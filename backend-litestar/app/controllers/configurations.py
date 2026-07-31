from typing import Any

from litestar import Router, get, post, put, delete
from litestar.exceptions import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Configuration, Deployment, MLModel
from app.schemas import configuration_dict


async def _expand_with_children(db_session: AsyncSession, model_ids: list[int]) -> list[int]:
    """A distributed model's parts form a father -> child -> child... chain
    (MLModel.father, self-referential one-to-one). Selecting a model for a
    configuration must pull in its whole chain, not just the one id the
    frontend sent."""
    all_ids: list[int] = []
    for model_id in model_ids:
        all_ids.append(model_id)
        current_id = model_id
        while True:
            result = await db_session.execute(
                select(MLModel.id).where(MLModel.father_id == current_id)
            )
            child_id = result.scalar_one_or_none()
            if child_id is None:
                break
            all_ids.append(child_id)
            current_id = child_id
    return all_ids


@get("/configurations/", tags=["configurations"])
async def list_configurations(db_session: AsyncSession) -> list[dict[str, Any]]:
    result = await db_session.execute(
        select(Configuration).options(
            selectinload(Configuration.ml_models), selectinload(Configuration.deployments)
        )
    )
    return [configuration_dict(c) for c in result.scalars().all()]


@post("/configurations/", tags=["configurations"])
async def create_configuration(data: dict[str, Any], db_session: AsyncSession) -> None:
    try:
        expanded_ids = await _expand_with_children(db_session, data["ml_models"])
        models = list((await db_session.execute(
            select(MLModel).where(MLModel.id.in_(expanded_ids))
        )).scalars().all())

        configuration = Configuration(
            name=data["name"], description=data.get("description", ""), ml_models=models
        )
        db_session.add(configuration)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Configuration not valid") from e


@get("/configurations/{configuration_id:int}", tags=["configurations"])
async def get_configuration(configuration_id: int, db_session: AsyncSession) -> dict[str, Any]:
    configuration = await db_session.get(
        Configuration,
        configuration_id,
        options=[selectinload(Configuration.ml_models), selectinload(Configuration.deployments)],
    )
    if configuration is None:
        raise HTTPException(status_code=400, detail="Configuration does not exist")
    return configuration_dict(configuration)


@put("/configurations/{configuration_id:int}", tags=["configurations"])
async def update_configuration(
    configuration_id: int, data: dict[str, Any], db_session: AsyncSession
) -> None:
    configuration = await db_session.get(
        Configuration, configuration_id, options=[selectinload(Configuration.ml_models)]
    )
    if configuration is None:
        raise HTTPException(status_code=400, detail="Configuration does not exist")

    try:
        expanded_ids = await _expand_with_children(db_session, data["ml_models"])
        models = list((await db_session.execute(
            select(MLModel).where(MLModel.id.in_(expanded_ids))
        )).scalars().all())

        configuration.name = data.get("name", configuration.name)
        configuration.description = data.get("description", configuration.description)
        configuration.ml_models = models
    except Exception as e:
        raise HTTPException(status_code=400, detail="Information not valid") from e


@delete("/configurations/{configuration_id:int}", tags=["configurations"], status_code=200)
async def delete_configuration(configuration_id: int, db_session: AsyncSession) -> None:
    configuration = await db_session.get(Configuration, configuration_id)
    if configuration is None:
        raise HTTPException(status_code=400, detail="Model does not exist")

    in_use = await db_session.execute(
        select(Deployment.id).where(Deployment.configuration_id == configuration_id)
    )
    if in_use.first() is not None:
        raise HTTPException(
            status_code=400,
            detail="Configuration cannot be deleted since it is used by a deployment. "
            "Consider to delete the deployment.",
        )
    await db_session.delete(configuration)


@get("/frameworksInConfiguration/{configuration_id:int}", tags=["configurations"])
async def used_frameworks(configuration_id: int, db_session: AsyncSession) -> list[str]:
    configuration = await db_session.get(
        Configuration, configuration_id, options=[selectinload(Configuration.ml_models)]
    )
    if configuration is None:
        raise HTTPException(status_code=400, detail="Configuration does not exist")
    return sorted({m.framework for m in configuration.ml_models})


@get("/distributedConfiguration/{configuration_id:int}", tags=["configurations"])
async def is_distributed_configuration(configuration_id: int, db_session: AsyncSession) -> bool:
    configuration = await db_session.get(
        Configuration, configuration_id, options=[selectinload(Configuration.ml_models)]
    )
    if configuration is None:
        raise HTTPException(status_code=400, detail="Configuration does not exists")
    return any(m.distributed for m in configuration.ml_models)


router = Router(
    path="/",
    route_handlers=[
        list_configurations,
        create_configuration,
        get_configuration,
        update_configuration,
        delete_configuration,
        used_frameworks,
        is_distributed_configuration,
    ],
)
