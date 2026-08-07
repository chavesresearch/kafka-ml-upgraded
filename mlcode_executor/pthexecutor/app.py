import json
import logging
import multiprocessing
import os
from queue import Empty
from typing import Any, Optional

import numpy as np

import torch
from torch import nn
from torch.utils.data import TensorDataset, DataLoader
from torchinfo import summary
from torchvision.transforms import ToTensor
import torchvision.models as models

# Wildcard on purpose: `exec_model` below runs user-submitted model code in
# this module's globals(), so names like Accuracy/Precision/Recall/etc. need
# to already be bound here for that code to reference them unqualified, even
# though only Loss is used directly in this file. Don't narrow to an
# explicit import.
from ignite.metrics import *
from ignite.engine import create_supervised_trainer, create_supervised_evaluator

from litestar import Litestar, Request, post
from litestar.datastructures import UploadFile
from litestar.response import Response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def exec_model(imports_code, model_code, distributed):
    """Runs the ML code and returns the generated model
        Args:
            imports_code (str): Imports before the code
            model_code (str): ML code to run
        Returns:
            model: generated model from the code
    """

    if imports_code is not None and imports_code!='':
        """Checks if there is any import to be executed before the code"""
        exec (imports_code, None, globals())

    exec (model_code, None, globals())

    return model


# Wall-clock cap on exec()'d model code. Generous - real model-building
# code is milliseconds to low seconds - but bounded, so a submission with
# an infinite loop can't tie up this service forever.
EXEC_TIMEOUT_S = 60


def _exec_pth_worker(imports_code, model_code, distributed, request_type, result_queue) -> None:
    """Runs in a *subprocess* (see pytorch_executor below for why) - do all
    model-dependent work here, not just exec_model() itself, since an
    nn.Module isn't reliably picklable back across the process boundary.
    Only json/str-safe results go on the queue.
    """
    try:
        model = exec_model(imports_code, model_code, distributed)
        if request_type == "check":
            summary(model)

            # Some checks to ensure the model is well defined for Kafka-ML
            logger.info(model.loss_fn())
            logger.info(model.optimizer())
            logger.info(model.metrics())

            logger.info(type(model.metrics()["loss"]._loss_fn) == type(model.loss_fn()))

            result_queue.put(("ok", b""))
        elif request_type == "input_shape":
            # TODO: https://stackoverflow.com/questions/66488807/pytorch-model-input-shape ??
            input_shape = next(model.parameters()).size()
            result_queue.put(("ok", str(input_shape)))
        else:
            result_queue.put(("not_found", None))
    except Exception as e:
        result_queue.put(("error", str(e)))


@post("/exec_pth/", sync_to_thread=True)
def pytorch_executor(data: dict[str, Any]) -> Response:
    logger.info("Data code received %s", data)

    # Remove pretrained=True
    data['model_code'] = data['model_code'].replace("pretrained=True", "pretrained=False")

    # exec()'d code runs in a genuinely killable child process, not this
    # thread - see tfexecutor/app.py's tensorflow_executor for the full
    # reasoning (same fix, same root cause, independent services).
    ctx = multiprocessing.get_context("spawn")
    result_queue = ctx.Queue()
    process = ctx.Process(
        target=_exec_pth_worker,
        args=(data['imports_code'], data['model_code'], data['distributed'], data['request_type'], result_queue),
    )
    process.start()

    # Must read from the queue *before* join()ing - see tfexecutor/app.py's
    # tensorflow_executor for the full explanation of the deadlock this
    # avoids (a child blocked inside put() on a full pipe buffer will never
    # exit while join() is waiting for it to exit first). Today's payloads
    # here are small (b"" or a short shape string), so this exact deadlock
    # is latent rather than reproducing yet - fixed anyway for the same
    # correctness reason and to stay identical to the sibling service.
    try:
        status, payload = result_queue.get(timeout=EXEC_TIMEOUT_S)
    except Empty:
        status, payload = None, None
    finally:
        process.join(5)
        if process.is_alive():
            process.terminate()
            process.join(5)
            if process.is_alive():
                process.kill()
                process.join()

    if status is None:
        logger.error(
            "exec_pth timed out after %ss or exited without a result (exitcode %s)",
            EXEC_TIMEOUT_S, process.exitcode,
        )
        return Response(content=b"", status_code=400)

    if status == "ok":
        if data['request_type'] == 'input_shape':
            return Response(content=payload, media_type="text/plain", status_code=200)
        return Response(content=b"", status_code=200)
    elif status == "not_found":
        return Response(content=b"", status_code=404)
    else:
        logger.error("exec_pth failed: %s", payload)
        return Response(content=b"", status_code=400)

def _validate_model_worker(imports_code, model_code, weights_path, result_queue) -> None:
    """Runs in a subprocess, same reasoning as `_exec_pth_worker` above -
    `model_code` is exec()'d user-submitted code, and building the
    untrained module + loading a (potentially malformed/huge) state dict
    onto it should be killable the same way `/exec_pth/` already is, not
    run in-process."""
    try:
        model = exec_model(imports_code, model_code, False)
        state_dict = torch.load(weights_path, map_location="cpu")
        model.load_state_dict(state_dict)
        result_queue.put(("ok", b""))
    except Exception as e:
        result_queue.put(("error", str(e)))


@post("/validate_model/")
async def validate_model(request: Request) -> Response:
    """Used by backend's `POST /deployments/import` (importing an
    already-trained model for inference, without a real training Job) to
    confirm an uploaded `.pth` state dict actually loads onto the model
    built from `model_code`/`imports_code` before the import is accepted.
    Unlike tfexecutor's `.h5`-as-field-name convention, this is a new
    endpoint with no legacy wire contract to match - fixed field names.
    """
    form = await request.form()

    imports_code = form.get("imports_code") or ""
    model_code = form.get("model_code")
    weights_file = form.get("trained_model")

    if not isinstance(model_code, str) or not isinstance(weights_file, UploadFile):
        return Response(
            content="Missing required fields: 'model_code' or 'trained_model'.",
            media_type="text/plain",
            status_code=400,
        )

    os.makedirs('./tmp', exist_ok=True)
    weights_path = os.path.join('./tmp', 'validate_weights.pth')
    with open(weights_path, 'wb') as f:
        f.write(await weights_file.read())

    try:
        ctx = multiprocessing.get_context("spawn")
        result_queue = ctx.Queue()
        process = ctx.Process(
            target=_validate_model_worker,
            args=(imports_code, model_code, weights_path, result_queue),
        )
        process.start()

        # Same read-before-join ordering as pytorch_executor above, for the
        # same deadlock-avoidance reason.
        try:
            status, payload = result_queue.get(timeout=EXEC_TIMEOUT_S)
        except Empty:
            status, payload = None, None
        finally:
            process.join(5)
            if process.is_alive():
                process.terminate()
                process.join(5)
                if process.is_alive():
                    process.kill()
                    process.join()
    finally:
        if os.path.exists(weights_path):
            os.remove(weights_path)

    if status == "ok":
        return Response(content=b"", status_code=200)
    if status is None:
        logger.error(
            "validate_model timed out after %ss or exited without a result (exitcode %s)",
            EXEC_TIMEOUT_S, process.exitcode,
        )
        return Response(content=b"timed out", media_type="text/plain", status_code=400)

    logger.error("validate_model failed: %s", payload)
    return Response(content=str(payload), media_type="text/plain", status_code=400)


def get_sample_data(batch):
    x_train_data = ToTensor()(np.random.random((batch, 1)))
    y_train_data = ToTensor()(np.random.random((batch, 1)))
    x_test_data  = ToTensor()(np.random.random((batch, 1)))
    y_test_data  = ToTensor()(np.random.random((batch, 1)))

    ds_train = TensorDataset(x_train_data, y_train_data)
    ds_test  = TensorDataset(x_test_data , y_test_data )

    train_dataloader = DataLoader(ds_train, batch_size=batch)
    test_dataloader  = DataLoader(ds_test, batch_size=batch)

    return train_dataloader, test_dataloader

def get_sample_model():
    class SampleNeuralNetwork(nn.Module):
        def __init__(self):
            super(SampleNeuralNetwork, self).__init__()
            self.samplelayer = nn.Sequential(
                nn.Linear(1, 10),
                nn.Linear(10, 1),
                nn.Softmax(1)
            )

        def forward(self, x):
            logits = self.samplelayer(x)
            return logits

        def loss_fn(self):
            return nn.MSELoss()

        def optimizer(self):
            return torch.optim.RMSprop(tf_executor_sample_model.parameters())

        def metrics(self):
            val_metrics = {
                "loss": Loss(self.loss_fn())
            }
            return val_metrics

    tf_executor_sample_model = SampleNeuralNetwork()

    return tf_executor_sample_model

def split_fit_params(fn_kwargs_fit: dict):
  fit_dataloader_list = ["shuffle", "sampler", "batch_sampler", "num_workers", "collate_fn", "pin_memory", "drop_last", "timeout",
                         "worker_init_fn", "multiprocessing_context", "generator", "prefetch_factor", "persistent_workers"]
  trainer_list = ["non_blocking", "prepare_batch", "output_transform", "deterministic", "amp_mode", "scaler", "gradient_accumulation_steps"]
  fit_run_list = ["max_epochs", "epoch_length"]

  fit_dataloader_kwargs, trainer_kwargs, fit_run_kwargs = dict(), dict(), dict()

  for args in list(fn_kwargs_fit.keys()):
    if args in fit_dataloader_list:
      fit_dataloader_kwargs[args]=fn_kwargs_fit[args]
    elif args in trainer_list:
      trainer_kwargs[args]=fn_kwargs_fit[args]
    elif args in fit_run_list:
      fit_run_kwargs[args]=fn_kwargs_fit[args]

  return fit_dataloader_kwargs, trainer_kwargs, fit_run_kwargs

def split_val_params(fn_kwargs_val: dict):
  val_dataloader_list = ["shuffle", "sampler", "batch_sampler", "num_workers", "collate_fn", "pin_memory", "drop_last", "timeout",
                         "worker_init_fn", "multiprocessing_context", "generator", "prefetch_factor", "persistent_workers"]
  validator_list = ["non_blocking", "prepare_batch", "output_transform", "amp_mode"]
  val_run_list = ["max_epochs", "epoch_length"]

  val_dataloader_kwargs, validator_kwargs, val_run_kwargs = dict(), dict(), dict()

  for args in list(fn_kwargs_val.keys()):
    if args in val_dataloader_list:
      val_dataloader_kwargs[args]=fn_kwargs_val[args]
    elif args in validator_list:
      validator_kwargs[args]=fn_kwargs_val[args]
    elif args in val_run_list:
      val_run_kwargs[args]=fn_kwargs_val[args]

  return val_dataloader_kwargs, validator_kwargs, val_run_kwargs


@post("/check_deploy_config/", sync_to_thread=True)
def check_deploy_config(data: dict[str, Any]) -> Response:
    try:
        logger.info("Data code received %s", data)

        data['kwargs_fit'] = json.loads(data['kwargs_fit'].replace("'", '"'))
        data['kwargs_val'] = json.loads(data['kwargs_val'].replace("'", '"'))

        assert data['kwargs_fit']['max_epochs'] > 0 and type(data['kwargs_fit']['max_epochs']) == int
        data['kwargs_fit']['max_epochs'] = 1

        _, trainer_kwargs, fit_run_kwargs   = split_fit_params(data['kwargs_fit'])
        _, validator_kwargs, val_run_kwargs = split_val_params(data['kwargs_val'])

        train, test = get_sample_data(data['batch'])
        tf_executor_model = get_sample_model().double()

        trainer = create_supervised_trainer(tf_executor_model, tf_executor_model.optimizer(), tf_executor_model.loss_fn(), "cpu", **trainer_kwargs)
        train_evaluator = create_supervised_evaluator(tf_executor_model, metrics=tf_executor_model.metrics(), device="cpu", **validator_kwargs)

        trainer.run(train, **fit_run_kwargs)
        train_evaluator.run(train, **val_run_kwargs)

        val_evaluator = create_supervised_evaluator(tf_executor_model, metrics=tf_executor_model.metrics(), device="cpu", **validator_kwargs)
        val_evaluator.run(test, **val_run_kwargs)

        return Response(content=b"", status_code=200)
    except Exception as e:
        logger.error(str(e))
        return Response(content=b"", status_code=400)


app = Litestar(route_handlers=[pytorch_executor, check_deploy_config, validate_model])
