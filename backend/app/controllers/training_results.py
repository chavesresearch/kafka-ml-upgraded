import json
import logging
import os
from typing import Annotated, Any, Optional

import anyio
import httpx
import msgspec
from kubernetes_asyncio import client as k8s_client, config as k8s_config
from litestar import Router, get, post, delete
from litestar.datastructures import UploadFile
from litestar.enums import RequestEncodingType
from litestar.exceptions import HTTPException
from litestar.params import Body
from litestar.response import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models import TrainingResult
from app.schemas import training_result_dict
from app.utils import kubernetes_api_client

logger = logging.getLogger(__name__)

_METRIC_FIELDS = ("train_metrics", "val_metrics", "test_metrics", "confusion_matrix", "training_time")


@get("/results/", tags=["results"])
async def list_results(db_session: AsyncSession) -> list[dict[str, Any]]:
    result = await db_session.execute(
        select(TrainingResult).options(
            selectinload(TrainingResult.deployment), selectinload(TrainingResult.model)
        )
    )
    return [training_result_dict(r) for r in result.scalars().all()]


@get("/results/{result_id:int}", tags=["results"])
async def get_result_model_file(
    result_id: int, db_session: AsyncSession, http_client: httpx.AsyncClient
) -> Response:
    """Fetches the (re-built, for tf) or raw (for pth) model architecture
    file for a training job to load. Also bumps the result's status from
    `created` to `deployed` on first fetch."""
    result = await db_session.get(
        TrainingResult, result_id, options=[selectinload(TrainingResult.model)]
    )
    if result is None:
        raise HTTPException(status_code=400, detail="TrainingResult not found")

    if result.model.framework == "tf":
        data_to_send = {
            "imports_code": result.model.imports,
            "model_code": result.model.code,
            "distributed": result.model.distributed,
            "request_type": "load_model",
        }
        resp = await http_client.post(
            settings.TENSORFLOW_EXECUTOR_URL + "exec_tf/", content=json.dumps(data_to_send)
        )
        response = Response(
            content=resp.content,
            media_type="application/model",
            headers={"Content-Disposition": 'attachment; filename="model.h5"'},
        )
    elif result.model.framework == "pth":
        response = Response(content=result.model.code, media_type="text/html")
    else:
        raise HTTPException(status_code=400, detail="Unknown framework")

    if result.status != "finished":
        result.status = "deployed"

    return response


class MetricsUpload(msgspec.Struct):
    data: str


@post("/results_metrics/{result_id:int}", tags=["results"], status_code=200)
async def upload_epoch_metrics(
    result_id: int,
    data: Annotated[MetricsUpload, Body(media_type=RequestEncodingType.URL_ENCODED)],
    db_session: AsyncSession,
) -> None:
    """Uploaded once per training epoch with the running `train_metrics`/
    `val_metrics` series so far (see model_training's callbacks.py)."""
    result = await db_session.get(TrainingResult, result_id)
    if result is None:
        raise HTTPException(status_code=400, detail="Training result does not exist")

    try:
        payload = json.loads(data.data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if "train_metrics" in payload:
        result.train_metrics = payload["train_metrics"]
    if "val_metrics" in payload:
        result.val_metrics = payload["val_metrics"]


class TrainingResultUpload(msgspec.Struct):
    data: str
    trained_model: UploadFile
    confussion_matrix: Optional[UploadFile] = None


@post("/results/{result_id:int}", tags=["results"], status_code=200)
async def upload_result(
    result_id: int,
    data: Annotated[TrainingResultUpload, Body(media_type=RequestEncodingType.MULTI_PART)],
    db_session: AsyncSession,
) -> None:
    result = await db_session.get(
        TrainingResult,
        result_id,
        options=[selectinload(TrainingResult.model), selectinload(TrainingResult.deployment)],
    )
    if result is None:
        raise HTTPException(status_code=400, detail="File not found")

    try:
        metrics = json.loads(data.data)

        if metrics.get("indefinite", False):
            # Continuous ("indefinite") incremental training: each round gets
            # its own TrainingResult row: the one named by `result_id` keeps
            # running, this new one records the round that just finished.
            result = TrainingResult(deployment=result.deployment, model=result.model)
            db_session.add(result)
            await db_session.flush()
            metrics.pop("indefinite")

        for field in _METRIC_FIELDS:
            if field in metrics:
                setattr(result, field, metrics[field])

        confussion_matrix_file = None
        if not result.model.distributed and result.deployment.conf_mat_settings and result.test_metrics not in (None, {}):
            confussion_matrix_file = data.confussion_matrix

        settings.MEDIA_ROOT.joinpath(settings.TRAINED_MODELS_DIR).mkdir(parents=True, exist_ok=True)
        trained_dir = settings.MEDIA_ROOT / settings.TRAINED_MODELS_DIR

        if confussion_matrix_file is not None:
            image_path = trained_dir / f"{result.id}.png"
            image_path.write_bytes(await confussion_matrix_file.read())
            result.confusion_mat_img_path = settings.TRAINED_MODELS_DIR + f"{result.id}.png"

        if result.model.framework == "tf":
            model_path = trained_dir / f"{result.id}.h5"
            model_path.write_bytes(await data.trained_model.read())
            result.trained_model_path = settings.TRAINED_MODELS_DIR + f"{result.id}.h5"
        elif result.model.framework == "pth":
            model_path = trained_dir / f"{result.id}.pth"
            model_path.write_bytes(await data.trained_model.read())
            result.trained_model_path = settings.TRAINED_MODELS_DIR + f"{result.id}.pth"

        result.status = "finished"
    except HTTPException:
        raise
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=400, detail=str(e)) from e


async def _find_training_job_name(batch_api: k8s_client.BatchV1Api, result_id: int) -> str | None:
    """Finds the Kubernetes Job training a given result.

    Job names aren't simply ``model-training-{result_id}`` in this port -
    `job_manifest_generator.py` uses different prefixes per mode (plain/
    incremental/federated/blockchain) and, for a distributed chain, ONE
    job trains every submodel's result together, with every result id
    appended to the name (e.g. ``distributed-model-training-7-8-9``).
    Reconstructing that naming byte-for-byte here (chain order, mode
    dispatch) would duplicate `create_deployment`'s own dispatch logic and
    drift the moment either changes. Listing Jobs and matching by the
    trailing dash-separated id segments instead is naming-scheme-agnostic
    and self-updating.
    """
    jobs = await batch_api.list_namespaced_job(namespace=settings.KUBE_NAMESPACE)
    for job in jobs.items:
        name = job.metadata.name
        ids: list[int] = []
        for part in reversed(name.split("-")):
            if not part.isdigit():
                break
            ids.append(int(part))
        if result_id in ids:
            return name
    return None


@post("/results/stop/{result_id:int}", tags=["results"], status_code=200)
async def stop_result(result_id: int, db_session: AsyncSession) -> None:
    """Stops a currently-training result: deletes its Kubernetes training
    Job (best-effort - a Job that already finished/was already deleted is
    not an error) and marks it ``stopped``.

    Mirrors the original Django `TrainingResultStop` view's contract
    (`POST /results/stop/{pk}`, only valid while `status == "deployed"`) -
    this port never implemented it at all (a real gap: the frontend's
    "Stop" action called it and always got a 404). Job-name resolution is
    the one real behavior change - see `_find_training_job_name` for why
    a lookup is more correct here than Django's hardcoded
    `"model-training-" + str(pk)` (which was never right for
    incremental/distributed/federated jobs to begin with).
    """
    result = await db_session.get(TrainingResult, result_id)
    if result is None or result.status != "deployed":
        raise HTTPException(status_code=400, detail="Result not found or not running")

    k8s_config.load_incluster_config()
    api_client = kubernetes_api_client(
        token=os.environ.get("KUBE_TOKEN"), external_host=os.environ.get("KUBE_HOST")
    )
    async with api_client:
        batch_api = k8s_client.BatchV1Api(api_client)
        try:
            job_name = await _find_training_job_name(batch_api, result_id)
            if job_name is not None:
                await batch_api.delete_namespaced_job(
                    name=job_name,
                    namespace=settings.KUBE_NAMESPACE,
                    body=k8s_client.V1DeleteOptions(
                        propagation_policy="Foreground", grace_period_seconds=5
                    ),
                )
        except Exception as e:
            # Best-effort, matching the original view: the Job may have
            # already finished/been cleaned up (ttlSecondsAfterFinished)
            # between the status check above and this call - the result
            # is still marked stopped either way, same as Django's version
            # swallowed this and proceeded.
            logger.error("Failed to delete training job for result %s: %s", result_id, str(e))

    result.status = "stopped"


@delete("/results/{result_id:int}", tags=["results"], status_code=200)
async def delete_result(result_id: int, db_session: AsyncSession) -> None:
    result = await db_session.get(TrainingResult, result_id)
    if result is None:
        raise HTTPException(status_code=400, detail="Result does not exist")
    if result.status not in ("finished", "stopped"):
        raise HTTPException(
            status_code=400, detail="Training result in use, please stop it before delete."
        )

    if result.trained_model_path:
        file_path = settings.MEDIA_ROOT / result.trained_model_path
        if file_path.exists():
            os.remove(file_path)

    await db_session.delete(result)


@get("/results/chart/{result_id:int}", tags=["results"])
async def get_result_metrics_chart(result_id: int, db_session: AsyncSession) -> dict[str, Any]:
    result = await db_session.get(TrainingResult, result_id)
    if result is None:
        raise HTTPException(status_code=400, detail="Training result does not exist")

    try:
        exists_valid = bool(result.val_metrics)

        series: list[dict[str, Any]] = []
        for metric, values in (result.train_metrics or {}).items():
            train_series = {
                "name": metric,
                "series": [{"value": v, "name": i + 1} for i, v in enumerate(values)],
            }
            series.append(train_series)

            if exists_valid:
                val_values = result.val_metrics.get(metric, [])
                series.append(
                    {
                        "name": f"{metric}_val",
                        "series": [{"value": v, "name": i + 1} for i, v in enumerate(val_values)],
                    }
                )

        return {"metrics": series, "conf_mat": result.confusion_matrix}
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=400, detail="Information not valid") from e


@get("/results/model/{result_id:int}", tags=["results"])
async def download_trained_model(result_id: int, db_session: AsyncSession) -> Response:
    result = await db_session.get(
        TrainingResult, result_id, options=[selectinload(TrainingResult.model)]
    )
    if result is None:
        raise HTTPException(status_code=400, detail="Result not found")

    try:
        file_path = settings.MEDIA_ROOT / result.trained_model_path
        # Offloaded to a thread - this is a single-worker event loop, and a
        # large trained-model file read would otherwise block every other
        # in-flight request (including the live /ws/ relay) for its
        # duration. See iot_devices.py's deploy_to_iot_devices for the
        # same fix applied to its own model-file read.
        content = await anyio.to_thread.run_sync(file_path.read_bytes)
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=400, detail=str(e)) from e

    file_ext = "h5" if result.model.framework == "tf" else "pth"
    return Response(
        content=content,
        media_type="application/force-download",
        headers={
            "Content-Disposition": f'attachment; filename="model.{file_ext}"',
            "Access-Control-Expose-Headers": "ML-Framework",
            "ML-Framework": result.model.framework,
        },
    )


@get("/results/confusion_matrix/{result_id:int}", tags=["results"])
async def download_confusion_matrix(result_id: int, db_session: AsyncSession) -> Response:
    result = await db_session.get(TrainingResult, result_id)
    if result is None:
        raise HTTPException(status_code=400, detail="Result not found")

    try:
        file_path = settings.MEDIA_ROOT / (result.confusion_mat_img_path or "")
        content = await anyio.to_thread.run_sync(file_path.read_bytes)
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=400, detail=str(e)) from e

    return Response(
        content=content,
        media_type="application/image",
        headers={"Content-Disposition": 'attachment; filename="confusion_mat.png'},
    )


router = Router(
    path="/",
    route_handlers=[
        list_results,
        get_result_model_file,
        upload_epoch_metrics,
        upload_result,
        stop_result,
        delete_result,
        get_result_metrics_chart,
        download_trained_model,
        download_confusion_matrix,
    ],
)
