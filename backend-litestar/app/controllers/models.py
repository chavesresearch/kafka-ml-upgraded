import json
import logging
from typing import Any

import httpx
from litestar import Router, get, post, put, delete
from litestar.exceptions import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models import Configuration, MLModel, TrainingResult
from app.schemas import model_dict

logger = logging.getLogger(__name__)


async def _check_model_code(http_client: httpx.AsyncClient, data: dict[str, Any]) -> bool:
    """Asks the matching mlcode_executor service to `exec()` the submitted
    code and report back whether it produces a usable model."""
    imports_code = data.get("imports", "")
    data_to_send = {
        "imports_code": imports_code,
        "model_code": data["code"],
        "distributed": data.get("distributed", False),
        "request_type": "check",
    }
    if data.get("framework") == "pth":
        url = settings.PYTORCH_EXECUTOR_URL + "exec_pth/"
    else:
        url = settings.TENSORFLOW_EXECUTOR_URL + "exec_tf/"

    resp = await http_client.post(url, content=json.dumps(data_to_send))
    return resp.status_code == 200


@get("/models/", tags=["models"])
async def list_models(db_session: AsyncSession) -> list[dict[str, Any]]:
    result = await db_session.execute(
        select(MLModel).options(selectinload(MLModel.father))
    )
    return [model_dict(m) for m in result.scalars().all()]


@post("/models/", tags=["models"])
async def create_model(
    data: dict[str, Any], db_session: AsyncSession, http_client: httpx.AsyncClient
) -> None:
    """Expects a JSON body with `name`, `code`, `framework` (and optionally
    `imports`, `distributed`, `father`). The submitted code is validated by
    running it in the matching (tf/pth) mlcode_executor service before it's
    persisted."""
    try:
        if not await _check_model_code(http_client, data):
            raise HTTPException(status_code=400, detail="Information not valid")

        father_id = data.get("father")
        model = MLModel(
            name=data["name"],
            description=data.get("description", ""),
            imports=data.get("imports", ""),
            code=data["code"],
            distributed=data.get("distributed", False),
            framework=data["framework"],
        )
        if model.distributed and father_id:
            father = await db_session.get(MLModel, father_id)
            if father is None:
                raise HTTPException(status_code=400, detail="Father model not found")
            model.father = father

        db_session.add(model)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=400, detail=str(e)) from e


@get("/models/distributed", tags=["models"])
async def list_distributed_models(db_session: AsyncSession) -> list[dict[str, Any]]:
    result = await db_session.execute(
        select(MLModel)
        .where(MLModel.distributed.is_(True))
        .options(selectinload(MLModel.father))
    )
    return [model_dict(m) for m in result.scalars().all()]


@get("/models/fathers", tags=["models"])
async def list_father_models(db_session: AsyncSession) -> list[dict[str, Any]]:
    result = await db_session.execute(
        select(MLModel)
        .where(MLModel.father_id.is_(None))
        .options(selectinload(MLModel.father))
    )
    return [model_dict(m) for m in result.scalars().all()]


@get("/models/result/{result_id:int}", tags=["models"])
async def get_model_by_result(result_id: int, db_session: AsyncSession) -> dict[str, Any]:
    """Returns the MLModel that produced a given TrainingResult.

    (In the original Django backend, ``ModelResultID`` accidentally defined
    two ``get`` methods in the same class body - a Python class only keeps
    the last one, so this endpoint's real implementation was shadowed by
    ~90 lines of copy-pasted, unrelated inference-deployment logic that
    belonged on ``InferenceResultID`` instead. The frontend's
    ``getModelResultID`` expects an MLModel shape back, so that bug broke
    the inference and inference-iot views. Fixed here.)
    """
    result = await db_session.execute(
        select(TrainingResult)
        .where(TrainingResult.id == result_id)
        .options(selectinload(TrainingResult.model).selectinload(MLModel.father))
    )
    training_result = result.scalar_one_or_none()
    if training_result is None:
        raise HTTPException(status_code=400, detail="TrainingResult not found")
    return model_dict(training_result.model)


@get("/models/{model_id:int}", tags=["models"])
async def get_model(model_id: int, db_session: AsyncSession) -> dict[str, Any]:
    model = await db_session.get(MLModel, model_id, options=[selectinload(MLModel.father)])
    if model is None:
        raise HTTPException(status_code=400, detail="Model does not exist")
    return model_dict(model)


@put("/models/{model_id:int}", tags=["models"])
async def update_model(
    model_id: int,
    data: dict[str, Any],
    db_session: AsyncSession,
    http_client: httpx.AsyncClient,
) -> None:
    model = await db_session.get(MLModel, model_id)
    if model is None:
        raise HTTPException(status_code=400, detail="Model does not exist")

    try:
        if data.get("code") != model.code or data.get("framework") != model.framework:
            if not await _check_model_code(http_client, data):
                raise HTTPException(status_code=400, detail="Model not valid.")

        model.name = data.get("name", model.name)
        model.description = data.get("description", model.description)
        model.imports = data.get("imports", model.imports)
        model.code = data.get("code", model.code)
        model.framework = data.get("framework", model.framework)
        model.distributed = data.get("distributed", model.distributed)

        if model.distributed:
            father_id = data.get("father")
            if father_id:
                if father_id == model.id:
                    raise HTTPException(
                        status_code=400, detail="A model can not be its own father"
                    )
                father = await db_session.get(MLModel, father_id)
                if father is None:
                    raise HTTPException(status_code=400, detail="Father model not found")
                model.father = father
        else:
            model.father = None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=400, detail="Information not valid") from e


@delete("/models/{model_id:int}", tags=["models"], status_code=200)
async def delete_model(model_id: int, db_session: AsyncSession) -> None:
    model = await db_session.get(MLModel, model_id)
    if model is None:
        raise HTTPException(status_code=400, detail="Model does not exist")

    in_use = await db_session.execute(
        select(Configuration.id).join(Configuration.ml_models).where(MLModel.id == model_id)
    )
    if in_use.first() is not None:
        raise HTTPException(
            status_code=400,
            detail="Model cannot be deleted since it is used in a configuration. "
            "Consider to delete the configuration.",
        )
    await db_session.delete(model)


router = Router(
    path="/",
    route_handlers=[
        list_models,
        create_model,
        list_distributed_models,
        list_father_models,
        get_model_by_result,
        get_model,
        update_model,
        delete_model,
    ],
)
