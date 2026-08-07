import json
import logging
import os
import re
from typing import Any

import httpx
from kubernetes_asyncio import client as k8s_client, config as k8s_config
from litestar import Router, get, delete
from litestar import post as litestar_post
from litestar.exceptions import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import job_manifest_generator
from app.config import settings
from app.models import Configuration, Deployment, MLModel, TrainingResult
from app.schemas import deployment_dict, training_result_dict
from app.utils import kubernetes_api_client, parse_kwargs_fit

logger = logging.getLogger(__name__)

_KWARGS_PATTERN = re.compile(
    r"^[A-Za-z0-9-_]*[ ]*=[ ]*[A-Za-z0-9-_]*[ ]*(,[ ]*[A-Za-z0-9-_]*[ ]*=[ ]*[A-Za-z0-9-_]*[ ]*)*$"
)

_PASSTHROUGH_FIELDS = (
    "optimizer",
    "learning_rate",
    "loss",
    "metrics",
    "incremental",
    "indefinite",
    "stream_timeout",
    "monitoring_metric",
    "change",
    "improvement",
    "unsupervised",
    "unsupervised_rounds",
    "confidence",
    "batch",
    "conf_mat_settings",
    "federated",
    "agg_rounds",
    "min_data",
    "agg_strategy",
    "data_restriction",
    "blockchain",
)


def _validate_kwargs_format(value: str) -> None:
    if not _KWARGS_PATTERN.match(value):
        raise HTTPException(
            status_code=400, detail="Arguments for training do not have the expected format"
        )


@get("/deployments/", tags=["deployments"])
async def list_deployments(db_session: AsyncSession) -> list[dict[str, Any]]:
    result = await db_session.execute(
        select(Deployment).options(
            selectinload(Deployment.configuration),
            selectinload(Deployment.results).selectinload(TrainingResult.model),
        )
    )
    return [deployment_dict(d) for d in result.scalars().all()]


async def _child_model_id(db_session: AsyncSession, model_id: int) -> int | None:
    result = await db_session.execute(select(MLModel.id).where(MLModel.father_id == model_id))
    return result.scalar_one_or_none()


@litestar_post("/deployments/", tags=["deployments"])
async def create_deployment(
    data: dict[str, Any], db_session: AsyncSession, http_client: httpx.AsyncClient
) -> None:
    """Expects a JSON body describing a deployment for a configuration
    (``configuration``: pk, plus batch/kwargs/incremental/federated/... settings,
    ``gpumem``: GPUs to allocate). Validates the tf/pth training kwargs against
    the matching mlcode_executor service, persists the Deployment and one
    TrainingResult per model in the configuration, then submits one
    Kubernetes training Job per (root) model.
    """
    gpu_mem_to_allocate = data.pop("gpumem", 0)

    tf_kwargs_fit_empty = tf_kwargs_val_empty = False
    if data.get("tf_kwargs_fit", "") != "":
        if data.get("tf_kwargs_val", "") == "":
            tf_kwargs_val_empty = True
            data.pop("tf_kwargs_val", None)
    else:
        data.pop("tf_kwargs_fit", None)
        data.pop("tf_kwargs_val", None)
        tf_kwargs_fit_empty = tf_kwargs_val_empty = True

    pth_kwargs_fit_empty = pth_kwargs_val_empty = False
    if data.get("pth_kwargs_fit", "") != "":
        if data.get("pth_kwargs_val", "") == "":
            pth_kwargs_val_empty = True
            data.pop("pth_kwargs_val", None)
    else:
        data.pop("pth_kwargs_fit", None)
        data.pop("pth_kwargs_val", None)
        pth_kwargs_fit_empty = pth_kwargs_val_empty = True

    for key in ("tf_kwargs_fit", "tf_kwargs_val", "pth_kwargs_fit", "pth_kwargs_val"):
        if key in data:
            _validate_kwargs_format(data[key])

    if data.get("batch", 1) <= 0:
        raise HTTPException(status_code=400, detail="Batch has to be greater than 0")

    configuration_id = data.get("configuration")
    configuration = await db_session.get(
        Configuration, configuration_id, options=[selectinload(Configuration.ml_models)]
    )
    if configuration is None:
        raise HTTPException(status_code=400, detail="Configuration not found")

    # PyTorch has no federated training at any layer - model_training/
    # pytorch/training.py has no CASE dispatch at all, and
    # federated-module/federated_model_training/pytorch doesn't exist
    # (see FUTURE.md's CASE_2_9_PLAN.md). Without this check, a PyTorch
    # model deployed as federated wouldn't error - it would silently run
    # plain classic training in a Job labeled/tracked as federated,
    # ignoring every federated setting. The frontend already gates this
    # (DeploymentView.tsx hides the checkbox when a PyTorch model is
    # detected), this is defense in depth for anyone calling the API
    # directly.
    if data.get("federated", False) and any(m.framework == "pth" for m in configuration.ml_models):
        raise HTTPException(
            status_code=400, detail="Federated learning is only supported for TensorFlow models."
        )

    # Real Kubernetes Jobs created for a root model earlier in the loop
    # below, tracked so a later model's failure can clean them up - see the
    # except block, this list is read there.
    created_job_names: list[str] = []

    try:
        tf_kwargs_fit = tf_kwargs_val = pth_kwargs_fit = pth_kwargs_val = None

        if not tf_kwargs_fit_empty:
            tf_kwargs_fit = parse_kwargs_fit(data["tf_kwargs_fit"])
            tf_kwargs_val = parse_kwargs_fit(data["tf_kwargs_val"]) if not tf_kwargs_val_empty else "{}"

            resp = await http_client.post(
                settings.TENSORFLOW_EXECUTOR_URL + "check_deploy_config/",
                content=json.dumps({"batch": data["batch"], "kwargs_fit": tf_kwargs_fit, "kwargs_val": tf_kwargs_val}),
            )
            if resp.status_code != 200:
                raise ValueError("Some TensorFlow arguments are not valid.")

            if data.get("incremental", False) and data.get("indefinite", False):
                for m in configuration.ml_models:
                    if not m.distributed and data.get("monitoring_metric") not in m.code:
                        raise ValueError("Monitoring metric does not match.")

        if not pth_kwargs_fit_empty:
            pth_kwargs_fit = parse_kwargs_fit(data["pth_kwargs_fit"])
            pth_kwargs_val = parse_kwargs_fit(data["pth_kwargs_val"]) if not pth_kwargs_val_empty else "{}"

            resp = await http_client.post(
                settings.PYTORCH_EXECUTOR_URL + "check_deploy_config/",
                content=json.dumps({"batch": data["batch"], "kwargs_fit": pth_kwargs_fit, "kwargs_val": pth_kwargs_val}),
            )
            if resp.status_code != 200:
                raise ValueError("Some PyTorch arguments are not valid.")

        deployment = Deployment(
            configuration=configuration,
            tf_kwargs_fit=data.get("tf_kwargs_fit", ""),
            tf_kwargs_val=data.get("tf_kwargs_val", ""),
            pth_kwargs_fit=data.get("pth_kwargs_fit", ""),
            pth_kwargs_val=data.get("pth_kwargs_val", ""),
            **{f: data[f] for f in _PASSTHROUGH_FIELDS if f in data},
        )
        db_session.add(deployment)
        await db_session.flush()

        results_by_model_id: dict[int, TrainingResult] = {}
        for model in configuration.ml_models:
            result = TrainingResult(model=model, deployment=deployment)
            db_session.add(result)
            results_by_model_id[model.id] = result
        await db_session.flush()

        # Real bug, found via an actual API-driven deployment test (not by
        # inspection): `kubernetes_asyncio.config.load_incluster_config` is
        # a *sync* function in kubernetes-asyncio==32.0.0 (confirmed with
        # `inspect.iscoroutinefunction` - returns `False`) - it returns
        # `None`, not a coroutine, so `await`ing it raised `TypeError:
        # object NoneType can't be used in 'await' expression` on every
        # single call, 100% of the time. This is the first time this
        # method has actually been exercised against a real cluster (the
        # original port's own CLAUDE.md flagged Job/RC creation as
        # untested for exactly this reason).
        k8s_config.load_incluster_config()
        api_client = kubernetes_api_client(
            token=os.environ.get("KUBE_TOKEN"), external_host=os.environ.get("KUBE_HOST")
        )
        async with api_client:
            batch_api = k8s_client.BatchV1Api(api_client)

            for model in configuration.ml_models:
                if model.distributed and model.father_id is not None:
                    continue  # only the chain's root model triggers a job

                result = results_by_model_id[model.id]
                if model.framework == "tf":
                    image = settings.TENSORFLOW_TRAINING_MODEL_IMAGE
                    kwargs_fit, kwargs_val = tf_kwargs_fit, tf_kwargs_val
                else:
                    image = settings.PYTORCH_TRAINING_MODEL_IMAGE
                    kwargs_fit, kwargs_val = pth_kwargs_fit, pth_kwargs_val

                if not model.distributed:
                    if not deployment.incremental:
                        if not deployment.federated:
                            job_manifest = job_manifest_generator.single_classic_training(
                                result, deployment, image, 1, kwargs_fit, kwargs_val, settings
                            )
                        else:
                            job_manifest = job_manifest_generator.single_federated_training(
                                result, deployment, image,
                                5 if not deployment.blockchain else 9,
                                kwargs_fit, kwargs_val, settings,
                            )
                    else:
                        if not deployment.federated:
                            job_manifest = job_manifest_generator.single_incremental_training(
                                result, deployment, image, 2, kwargs_fit, kwargs_val, settings
                            )
                        else:
                            job_manifest = job_manifest_generator.single_federated_incremental_training(
                                result, deployment, image, 6, kwargs_fit, kwargs_val, settings
                            )
                else:
                    result_urls, result_ids, n = [], [], ""
                    backend_results_url = str(os.environ.get("BACKEND_URL")) + "/results/"

                    result_urls.append(backend_results_url + str(result.id))
                    result_ids.append(str(result.id))
                    n += "-" + str(result.id)

                    current_model_id = model.id
                    while True:
                        child_id = await _child_model_id(db_session, current_model_id)
                        if child_id is None:
                            break
                        current_result = results_by_model_id[child_id]
                        result_urls.append(backend_results_url + str(current_result.id))
                        result_ids.append(str(current_result.id))
                        n += "-" + str(current_result.id)
                        current_model_id = child_id

                    result_urls.reverse()
                    result_ids.reverse()

                    if not deployment.incremental:
                        if not deployment.federated:
                            job_manifest = job_manifest_generator.distributed_classic_training(
                                n, result_urls, result_ids, deployment, image, 3, kwargs_fit, kwargs_val, settings
                            )
                        else:
                            job_manifest = job_manifest_generator.distributed_federated_training(
                                n, result_urls, result_ids, deployment, image, 7, kwargs_fit, kwargs_val, settings
                            )
                    else:
                        if not deployment.federated:
                            job_manifest = job_manifest_generator.distributed_incremental_training(
                                n, result_urls, result_ids, deployment, image, 4, kwargs_fit, kwargs_val, settings
                            )
                        else:
                            job_manifest = job_manifest_generator.distributed_federated_incremental_training(
                                n, result_urls, result_ids, deployment, image, 8, kwargs_fit, kwargs_val, settings
                            )

                if gpu_mem_to_allocate > 0:
                    container = job_manifest["spec"]["template"]["spec"]["containers"][0]
                    container["resources"] = {"limits": {"nvidia.com/gpu": gpu_mem_to_allocate}}
                    container["env"].append({"name": "NVIDIA_VISIBLE_DEVICES", "value": "all"})
                    job_manifest["spec"]["template"]["spec"]["runtimeClassName"] = "nvidia"

                resp = await batch_api.create_namespaced_job(
                    body=job_manifest, namespace=settings.KUBE_NAMESPACE
                )
                created_job_names.append(job_manifest["metadata"]["name"])
                logger.info("Job created. status='%s'", resp.status)
    except (ValueError, HTTPException):
        raise
    except Exception as e:
        # This request's DB transaction is about to roll back (Deployment/
        # TrainingResult rows disappear), but that can't undo a Job for an
        # earlier model in the loop above that was *already* submitted to
        # the real cluster before this one failed - left alone, it keeps
        # running and posts results against a result id that no longer
        # exists. Clean those up too, so a partial failure here doesn't
        # leave orphaned Jobs behind. Best-effort: a cleanup failure is
        # logged, not re-raised - the original error is still what the
        # caller sees, and an operator can still find/remove a leaked Job
        # manually via the logged name if this second call also fails.
        if created_job_names:
            try:
                cleanup_client = kubernetes_api_client(
                    token=os.environ.get("KUBE_TOKEN"), external_host=os.environ.get("KUBE_HOST")
                )
                async with cleanup_client:
                    cleanup_batch_api = k8s_client.BatchV1Api(cleanup_client)
                    for job_name in created_job_names:
                        try:
                            await cleanup_batch_api.delete_namespaced_job(
                                name=job_name,
                                namespace=settings.KUBE_NAMESPACE,
                                body=k8s_client.V1DeleteOptions(propagation_policy="Foreground"),
                            )
                        except Exception as cleanup_err:
                            logger.error("Failed to clean up orphaned Job %s: %s", job_name, cleanup_err)
            except Exception as cleanup_err:
                logger.error(
                    "Failed to clean up orphaned Jobs %s after a partial deployment failure: %s",
                    created_job_names, cleanup_err,
                )
        logger.error(str(e))
        raise HTTPException(status_code=400, detail=str(e)) from e


@get("/deployments/{pk:int}", tags=["deployments"])
async def list_deployments_for_configuration(pk: int, db_session: AsyncSession) -> list[dict[str, Any]]:
    """Despite the shared path, this mirrors the original API: GET treats
    ``pk`` as a Configuration id (list its deployments), while DELETE on the
    same path (below) treats ``pk`` as a Deployment id. That's the existing
    ``DeploymentsConfigurationID`` contract the Angular app already relies on."""
    configuration = await db_session.get(Configuration, pk)
    if configuration is None:
        raise HTTPException(status_code=400, detail="Configuration does not exist")

    result = await db_session.execute(
        select(Deployment)
        .where(Deployment.configuration_id == pk)
        .options(
            selectinload(Deployment.configuration),
            selectinload(Deployment.results).selectinload(TrainingResult.model),
        )
    )
    return [deployment_dict(d) for d in result.scalars().all()]


@delete("/deployments/{pk:int}", tags=["deployments"], status_code=200)
async def delete_deployment(pk: int, db_session: AsyncSession) -> None:
    deployment = await db_session.get(Deployment, pk)
    if deployment is None:
        raise HTTPException(status_code=400, detail="Deployment does not exist")

    has_results = (
        await db_session.execute(select(TrainingResult.id).where(TrainingResult.deployment_id == pk))
    ).first()
    if has_results is not None:
        raise HTTPException(
            status_code=400,
            detail="Deployment cannot be deleted. Please delete its training results first.",
        )
    await db_session.delete(deployment)


@get("/deployments/results/{pk:int}", tags=["deployments"])
async def get_deployment_results(pk: int, db_session: AsyncSession) -> list[dict[str, Any]]:
    deployment = await db_session.get(Deployment, pk)
    if deployment is None:
        raise HTTPException(status_code=400, detail="Deployment not found")

    result = await db_session.execute(
        select(TrainingResult)
        .where(TrainingResult.deployment_id == pk)
        .options(
            selectinload(TrainingResult.deployment), selectinload(TrainingResult.model)
        )
    )
    return [training_result_dict(r) for r in result.scalars().all()]


router = Router(
    path="/",
    route_handlers=[
        list_deployments,
        create_deployment,
        list_deployments_for_configuration,
        delete_deployment,
        get_deployment_results,
    ],
)
