import asyncio
import logging
from datetime import datetime
from typing import Any

from litestar import Router, post
from litestar.exceptions import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.kubernetes_deploy import deploy_on_kubernetes
from app.matching import check_colission
from app.models import Datasource, ModelSource

logger = logging.getLogger(__name__)

# Serializes the select-candidates -> deploy -> mark-consumed critical
# section across both handlers below. Without this, two registrations
# arriving close together can both SELECT the same counterpart row
# before either request's delete has committed - `await
# deploy_on_kubernetes(...)` is a real await point (Kubernetes API call
# latency), so the event loop can switch to the other request's coroutine
# mid-match, and both proceed to deploy against the same row (see
# FUTURE.md's Not-planned-turned-fixed entry for this bug). This service
# runs as a single uvicorn worker/process (start.sh has no --workers
# flag) with a SQLite backend (no real row-level locking available -
# SQLite is single-writer at the file level, `SELECT ... FOR UPDATE`
# isn't meaningful here), so a plain in-process asyncio.Lock is both
# sufficient and the simplest correct fix - it fully serializes matching
# across concurrent requests without needing a database-level primitive
# this backend doesn't have.
_match_lock = asyncio.Lock()


def _model_source_dict(m: ModelSource) -> dict[str, Any]:
    return {
        "federated_string_id": m.federated_string_id,
        "input_shape": m.input_shape,
        "output_shape": m.output_shape,
        "data_restriction": m.data_restriction,
        "min_data": m.min_data,
        "framework": m.framework,
        "distributed": m.distributed,
        "blockchain": m.blockchain,
    }


def _datasource_dict(d: Datasource) -> dict[str, Any]:
    return {
        "input_format": d.input_format,
        "input_config": d.input_config,
        "incremental": d.incremental,
        "topic": d.topic,
        "unsupervised_topic": d.unsupervised_topic,
        "total_msg": d.total_msg,
        "validation_rate": d.validation_rate,
        "test_rate": d.test_rate,
        "dataset_restrictions": d.dataset_restrictions,
    }


@post("/federated-datasources/", tags=["federated"])
async def create_datasource(data: dict[str, Any], db_session: AsyncSession) -> None:
    """Registers a new real Kafka datasource, then checks every pending
    ModelSource for a compatible match - same endpoint/behavior as the
    original Django ``DatasourceList.post``.

    Real fix vs. the original (see federated-module/CLAUDE.md's "Real-MNIST
    multi-epoch pass" + FUTURE.md High item 9): a matched ModelSource and
    Datasource are now deleted ("marked consumed") right after a
    successful match+deploy, instead of staying in the table forever to
    be re-scanned and potentially re-matched by every future registration
    - this is what let a single restart of the (separately fixed)
    control-logger services spawn duplicate edge worker Jobs from
    hours-old registrations.
    """
    try:
        topic = data["topic"]
        input_format = data["input_format"]
        time_str = data["time"]
    except KeyError as e:
        raise HTTPException(status_code=406, detail=f"Deployment not valid: missing {e}") from e

    datasource = Datasource(
        input_format=input_format,
        input_config=data.get("input_config", ""),
        incremental=data.get("incremental", False),
        topic=topic,
        unsupervised_topic=data.get("unsupervised_topic") or None,
        total_msg=data.get("total_msg"),
        validation_rate=data.get("validation_rate"),
        test_rate=data.get("test_rate"),
        description=data.get("description", ""),
        dataset_restrictions=data.get("dataset_restrictions", "{}"),
        time=datetime.fromisoformat(time_str),
    )
    db_session.add(datasource)
    await db_session.flush()

    ds_data = _datasource_dict(datasource)
    logger.info("Checking for models that can be trained...")

    async with _match_lock:
        result = await db_session.execute(select(ModelSource))
        for model_source in result.scalars().all():
            ms_data = _model_source_dict(model_source)

            if not ms_data["distributed"]:
                if not ds_data["incremental"]:
                    case = 1 if ms_data["blockchain"] == {} else 5
                else:
                    case = 2
            else:
                case = 4 if ds_data["incremental"] else 3

            if check_colission(ds_data, ms_data, case):
                logger.info("Datasource and model are compatible. Deploying model...")
                await deploy_on_kubernetes(ds_data, ms_data, ms_data["framework"], case)
                await db_session.delete(model_source)
                await db_session.delete(datasource)

        # Committed here, still inside the lock - not left for
        # provide_db_session's outer session.begin() to commit after this
        # handler returns. The lock alone only serializes the in-Python
        # critical section; without an early commit, a matched row's
        # delete stays invisible to the next lock-acquirer's own fresh
        # SELECT (each request gets its own AsyncSession) until this
        # request's transaction actually lands, reopening the exact same
        # race window at the database level instead of the event-loop
        # level.
        await db_session.commit()


@post("/model-control-logger/", tags=["federated"])
async def model_from_control_logger(data: dict[str, Any], db_session: AsyncSession) -> None:
    """Registers a new pending ModelSource, then checks every existing
    Datasource for a compatible match - same endpoint/behavior as the
    original Django ``ModelFromControlLogger.post``, including its
    already-fixed case dispatch and matching-loop guard (see
    federated-module/CLAUDE.md's "CASE 6-9" section: the original upstream
    code ignored ``incremental`` entirely here, so no federated-incremental
    model could ever be matched - fixed there, preserved here).

    Same mark-consumed fix as ``create_datasource`` above.
    """
    try:
        incremental = data["incremental"]
        federated_params = data["federated_params"]
        model_format = data["model_format"]
        framework = data["framework"]
        distributed = data["distributed"]
    except KeyError as e:
        raise HTTPException(status_code=406, detail=f"Deployment not valid: missing {e}") from e

    blockchain = data.get("blockchain", {})

    model_source = ModelSource(
        federated_string_id=federated_params["federated_string_id"],
        data_restriction=federated_params["data_restriction"],
        min_data=federated_params["min_data"],
        input_shape=model_format["input_shape"],
        output_shape=model_format["output_shape"],
        framework=framework,
        distributed=distributed,
        blockchain=blockchain,
    )
    db_session.add(model_source)
    await db_session.flush()

    ms_data = _model_source_dict(model_source)

    # Local edge-worker case numbering (federated_model_training/tensorflow/
    # utils.py's own 1-5 scheme, distinct from the main trainer's global
    # 1-9 CASE enum): 1=single, 2=single incremental, 3=distributed,
    # 4=distributed incremental, 5=blockchain (only defined for single,
    # non-incremental upstream).
    if not distributed:
        if blockchain != {}:
            case = 5
        elif not incremental:
            case = 1
        else:
            case = 2
    else:
        case = 4 if incremental else 3

    logger.info("Checking for datasources that can be used to train the model...")
    async with _match_lock:
        result = await db_session.execute(select(Datasource))
        for datasource in result.scalars().all():
            ds_data = _datasource_dict(datasource)

            # Non-incremental cases still wait for the datasource to have
            # finished sending (total_msg populated) - check_colission's own
            # case-based branch already skips the total_msg>=min_data
            # comparison for incremental cases (2, 4), so it doesn't need
            # gating here too.
            if incremental or ds_data["total_msg"] is not None:
                if check_colission(ds_data, ms_data, case):
                    logger.info("Datasource and model are compatible. Deploying model...")
                    await deploy_on_kubernetes(ds_data, ms_data, framework, case)
                    await db_session.delete(datasource)
                    await db_session.delete(model_source)

        # See create_datasource's identical comment above - committed
        # here, still inside the lock, so the next lock-acquirer's own
        # fresh SELECT can't still see a row this request already matched.
        await db_session.commit()


router = Router(path="/", route_handlers=[create_datasource, model_from_control_logger])
