import copy
import json
import logging
from typing import Any

from litestar import Router, get, post
from litestar.exceptions import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients import LazyKafkaProducer
from app.config import settings
from app.models import Datasource, Deployment
from app.schemas import datasource_dict

logger = logging.getLogger(__name__)


@get("/datasources/", tags=["datasources"])
async def list_datasources(db_session: AsyncSession) -> list[dict[str, Any]]:
    result = await db_session.execute(select(Datasource).order_by(Datasource.time.desc()))
    return [datasource_dict(d) for d in result.scalars().all()]


async def _create_datasource(
    data: dict[str, Any], db_session: AsyncSession, kafka_producer: LazyKafkaProducer
) -> None:
    """Expects a JSON body with the information about data that has just been
    sent to Kafka for a deployment, persists it, and forwards a control
    message to CONTROL_TOPIC so training jobs pick it up.

    (The original Django ``DatasourceList.post``/``DatasourceToKafka.post``
    validated this payload but never actually called ``.save()`` on it, so
    the ``Datasource`` table was permanently empty and ``GET /datasources/``
    could never return anything. Persisting it here so the record - and the
    input-format lookups in ``InferenceResultID`` that filter on it - work.)
    """
    try:
        deployment_id = int(data["deployment"])
        deployment_exists = (
            await db_session.execute(
                select(Deployment.id).where(Deployment.id == deployment_id)
            )
        ).first()
        if deployment_exists is None:
            raise HTTPException(status_code=400, detail="Deployment not valid")

        datasource = Datasource(
            input_format=data["input_format"],
            deployment=data["deployment"],
            input_config=data.get("input_config", ""),
            description=data.get("description", ""),
            topic=data["topic"],
            total_msg=data.get("total_msg"),
            validation_rate=data.get("validation_rate"),
            test_rate=data.get("test_rate"),
            time=data["time"],
        )
        db_session.add(datasource)

        kafka_data = copy.deepcopy(data)
        del kafka_data["deployment"]
        del kafka_data["time"]
        kafka_data["input_config"] = json.loads(kafka_data["input_config"])

        # 4-byte big-endian key: the original `bytes([deployment_id])` only
        # supported deployment ids 0-255 and raised ValueError above that.
        # Every consumer (model_training, mlcode_executor) decodes this key
        # generically via `int.from_bytes(msg.key, byteorder="big")`, so
        # widening it here stays wire-compatible with all of them.
        key = deployment_id.to_bytes(4, byteorder="big")
        value = json.dumps(kafka_data).encode("utf-8")

        logger.info("Control message to be sent to kafka control topic %s", kafka_data)
        await kafka_producer.send_and_wait(settings.CONTROL_TOPIC, key=key, value=value)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=400, detail=str(e)) from e


@post(["/datasources/", "/datasources/kafka"], tags=["datasources"])
async def create_datasource(
    data: dict[str, Any], db_session: AsyncSession, kafka_producer: LazyKafkaProducer
) -> None:
    await _create_datasource(data, db_session, kafka_producer)


router = Router(
    path="/",
    route_handlers=[list_datasources, create_datasource],
)
