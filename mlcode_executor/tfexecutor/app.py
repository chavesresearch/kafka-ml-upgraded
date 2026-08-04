import json
import logging
import os
from typing import Any, Optional

import anyio
import numpy as np
import tensorflow as tf
# `keras`/`tfds` aren't referenced directly in this file - they (along with
# `tf`/`np` above) are bound into this module's globals() so user-submitted
# model code (exec'd in this namespace by `exec_model` below) can reference
# them unqualified without having to import them itself. Don't remove as
# "unused".
from tensorflow import keras
import tensorflow_datasets as tfds
from kafka import KafkaConsumer
from litestar import Litestar, Request, post
from litestar.datastructures import UploadFile
from litestar.response import Response

from decoders import DecoderFactory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

gpus = tf.config.experimental.list_physical_devices('GPU')
for gpu in gpus:
    tf.config.experimental.set_memory_growth(gpu, True)
logger.info("Num GPUs Available: %d", len(tf.config.list_physical_devices('GPU')))


def format_ml_code(code):
    """Checks if the ML code ends with the string 'model = ' in its last line. Otherwise, it adds the string.
        Args:
            code (str): ML code to check
        Returns:
            str: code formatted
    """
    return code[:code.rfind('\n')+1] + 'model = ' + code[code.rfind('\n')+1:]

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

    if distributed:
        ml_code = format_ml_code(model_code)
        exec (ml_code, None, globals())
        """Runs the ML code"""
    else:
        exec (model_code, None, globals())

    return model

def get_sample_data(batch):
    x_train_data = np.random.random((batch, 1))
    y_train_data = np.random.random((batch, 1))
    x_test_data  = np.random.random((batch, 1))
    y_test_data  = np.random.random((batch, 1))

    ds_train = tf.data.Dataset.from_tensor_slices((x_train_data, y_train_data))
    ds_test = tf.data.Dataset.from_tensor_slices((x_test_data, y_test_data))

    return ds_train, ds_test

def get_sample_model():
    tf_executor_sample_model = tf.keras.models.Sequential([
        tf.keras.layers.Dense(10, activation='relu', input_shape=(1,)),
        tf.keras.layers.Dense(1, activation='softmax'),
    ])
    tf_executor_sample_model.compile(loss='mse', optimizer='rmsprop')

    return tf_executor_sample_model


@post("/exec_tf/", sync_to_thread=True)
def tensorflow_executor(data: dict[str, Any]) -> Response:
    try:
        logger.info("Data code received %s", data)
        model = exec_model(data['imports_code'], data['model_code'], data['distributed'])

        if data['request_type'] == "check":
            model.summary()
            return Response(content=b"", status_code=200)
        elif data['request_type'] == 'load_model':
            filename = "model.h5"
            model.save(filename)
            with open(filename, 'rb') as f:
                file_data = f.read()
            if os.path.exists(filename):
                os.remove(filename)
                """Removes the temporally file created"""
            return Response(content=file_data, media_type="application/octet-stream", status_code=200)
        elif data['request_type'] == 'input_shape':
            input_shape = str(model.input_shape)
            return Response(content=input_shape, media_type="text/plain", status_code=200)

        return Response(content=b"", status_code=404)
    except Exception as e:
        logger.error("exec_tf failed: %s", e)
        return Response(content=b"", status_code=400)


@post("/check_deploy_config/", sync_to_thread=True)
def check_deploy_config(data: dict[str, Any]) -> Response:
    try:
        logger.info("Data code received %s", data)

        data['kwargs_fit'] = json.loads(data['kwargs_fit'].replace("'", '"'))
        data['kwargs_val'] = json.loads(data['kwargs_val'].replace("'", '"'))

        assert data['kwargs_fit']['epochs'] > 0 and type(data['kwargs_fit']['epochs']) == int
        data['kwargs_fit']['epochs'] = 1

        train, test = get_sample_data(data['batch'])
        tf_executor_model = get_sample_model()

        tf_executor_model.fit(train, **data['kwargs_fit'])
        tf_executor_model.evaluate(test, **data['kwargs_val'])

        return Response(content=b"", status_code=200)
    except Exception as e:
        logger.error(str(e))
        return Response(content=b"", status_code=400)


def _consume_control_message(model_deployment_id: str, control_topic: str, bootstrap_servers: str, timeout: int = 60) -> Optional[dict]:
    """Waits (up to `timeout` seconds) on the Kafka control topic for the
    datasource metadata message matching `model_deployment_id`.
    Args:
        model_deployment_id (int): deployment id to match against the message key
        control_topic (str): Kafka control topic to consume
        bootstrap_servers (str): Kafka bootstrap servers
        timeout (int): max seconds to wait for the matching message
    Returns:
        dict: parsed datasource metadata, or None if no matching message arrived in time
    """
    consumer = KafkaConsumer(
        control_topic,
        bootstrap_servers=bootstrap_servers,
        auto_offset_reset='earliest',
        enable_auto_commit=False,
        consumer_timeout_ms=timeout * 1000,
    )
    try:
        for msg in consumer:
            if msg.key is None:
                continue
            received_deployment_id = int.from_bytes(msg.key, byteorder='big')
            if received_deployment_id == int(model_deployment_id):
                """Data received from Kafka control topic. Data is a JSON with this format:
                    dic={
                        'topic': ..,
                        'input_format': ..,
                        'input_config' : ..,
                        'description': ..,
                        'validation_rate' : ..,
                        'total_msg': ..
                    }
                """
                return json.loads(msg.value)
    finally:
        consumer.close()
    return None


def retrieve_representative_dataset(model_deployment_id: str, control_topic: str, bootstrap_servers: str, repr_data_size: int = 100):
    """Generator the TFLiteConverter calls to sample real Kafka data for int8
    calibration. Replaces the old `tensorflow_io.kafka.KafkaDataset`-based
    pipeline (tensorflow-io hasn't shipped a release since mid-2023 and caps
    out at TF 2.16) with a plain `kafka-python` consumer feeding the decoded
    messages straight into the converter.
    """
    control_data = _consume_control_message(model_deployment_id, control_topic, bootstrap_servers)
    if control_data is None:
        return

    decoder = DecoderFactory.get_decoder(control_data['input_format'], control_data['input_config'])
    topics = control_data['topic'].split(',')

    consumer = KafkaConsumer(
        *topics,
        bootstrap_servers=bootstrap_servers,
        group_id="TF_EXEC",
        auto_offset_reset='earliest',
        enable_auto_commit=False,
        consumer_timeout_ms=60000,
    )
    try:
        count = 0
        for msg in consumer:
            if count >= repr_data_size:
                break
            x, _y = decoder.decode(msg.value, msg.key)
            yield [tf.dtypes.cast(x, tf.float32)]
            count += 1
    finally:
        consumer.close()


def _convert_model_to_tflite(model_bytes: bytes, filename: str, quantization_params: dict) -> bytes:
    """Blocking TFLite conversion; run via `anyio.to_thread.run_sync` by the
    `convert_to_tflite` handler so it doesn't block the event loop.
    """
    os.makedirs('./tmp', exist_ok=True)
    model_path = os.path.join('./tmp', filename)
    with open(model_path, 'wb') as f:
        f.write(model_bytes)

    try:
        # compile=False: TFLiteConverter only needs the forward-pass graph
        # and weights, never the compiled loss/optimizer. Loading compiled
        # (the default) hits a real Keras 3 legacy-H5 bug for any model
        # whose loss was set via a string shorthand (e.g. 'mse') -
        # deserialization resolves it to `keras.metrics.mse` (a metric
        # function) instead of the loss class, then rejects it with
        # "Could not deserialize 'keras.metrics.mse' because it is not a
        # KerasSaveable subclass". Reproduced directly against a bare
        # `tf.keras.models.load_model()` call, independent of this service.
        model = tf.keras.models.load_model(model_path, compile=False)

        converter = tf.lite.TFLiteConverter.from_keras_model(model)

        if quantization_params["applyQuantization"]:
            if quantization_params["quantizationType"] == "dynamic":
                converter.optimizations = [tf.lite.Optimize.DEFAULT]
            elif quantization_params["quantizationType"] == "int8":
                converter.optimizations = [tf.lite.Optimize.DEFAULT]
                converter.representative_dataset = lambda: retrieve_representative_dataset(
                                                        quantization_params["modelDeploymentId"],
                                                        quantization_params["dataControlTopic"],
                                                        quantization_params["dataBootstrapServers"]
                                                    )
                converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
                converter.inference_input_type = tf.int8
                converter.inference_output_type = tf.int8

        # convert() already returns the flatbuffer bytes directly - no need
        # to round-trip through a .tflite file on disk like the old Flask
        # version did.
        return converter.convert()
    finally:
        if os.path.exists(model_path):
            os.remove(model_path)


@post("/convert_to_tflite/")
async def convert_to_tflite(request: Request) -> Response:
    form = await request.form()

    # The uploaded file's field name IS the model filename (e.g. "42.h5") -
    # matches how the backend posts it (`files={f"{result_id}.h5": ...}`),
    # so we look for a field ending in .h5 rather than a fixed field name.
    model_file: Optional[UploadFile] = None
    for name, value in form.items():
        if isinstance(value, UploadFile) and name.endswith('.h5'):
            model_file = value
            break

    if model_file is None:
        return Response(
            content="Invalid file type. Please upload a .h5 file.",
            media_type="text/plain",
            status_code=400,
        )

    quantization_params = {k: v for k, v in form.items() if isinstance(v, str)}
    quantization_params["applyQuantization"] = quantization_params["applyQuantization"].lower() == 'true'

    model_bytes = await model_file.read()

    try:
        tflite_bytes = await anyio.to_thread.run_sync(
            _convert_model_to_tflite, model_bytes, model_file.filename, quantization_params
        )
    except Exception as e:
        logger.error("TFLite conversion failed: %s", e)
        return Response(content=b"", status_code=400)

    return Response(content=tflite_bytes, media_type="application/octet-stream", status_code=200)


app = Litestar(route_handlers=[tensorflow_executor, check_deploy_config, convert_to_tflite])
