import logging
from datetime import datetime
from typing import Any

from litestar import Router, get, post
from litestar.exceptions import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Datasource, Deployment
from app.schemas import datasource_dict

logger = logging.getLogger(__name__)


@get("/datasources/", tags=["datasources"])
async def list_datasources(db_session: AsyncSession) -> list[dict[str, Any]]:
    result = await db_session.execute(select(Datasource).order_by(Datasource.time.desc()))
    return [datasource_dict(d) for d in result.scalars().all()]


async def _create_datasource(data: dict[str, Any], db_session: AsyncSession) -> None:
    """Expects a JSON body with the information about data that has just been
    sent to Kafka for a deployment, and persists it.

    (The original Django ``DatasourceList.post``/``DatasourceToKafka.post``
    validated this payload but never actually called ``.save()`` on it, so
    the ``Datasource`` table was permanently empty and ``GET /datasources/``
    could never return anything. Persisting it here so the record - and the
    input-format lookups in ``InferenceResultID`` that filter on it - work.

    This handler used to also re-publish the payload to ``CONTROL_TOPIC``
    ("so training jobs pick it up"). Removed: this endpoint only ever gets
    called *because* ``kafka_control_logger`` already consumed a message
    from that exact topic (published by the client-side ``KafkaMLSink``
    when it finishes sending data) and forwarded it here over HTTP.
    Re-publishing the same content back onto the topic it came from made
    ``kafka_control_logger`` see its own round-trip and forward it again -
    an unbounded loop that duplicated a ``Datasource`` row and re-published
    to Kafka for every single one, forever. Training jobs already consume
    ``CONTROL_TOPIC`` directly (matching on the deployment_id key), so
    nothing was actually relying on this handler's copy - it added no
    information the original client-published message didn't already have.)

    ``data["time"]`` is a JSON string (an ISO 8601 timestamp,
    ``kafka_control_logger`` sends ``datetime.isoformat()``) that needs
    parsing into a real ``datetime`` before it reaches the ``Datasource``
    model - ``dict[str, Any]``-style bodies skip the typed-field validation
    the original Django ``DatasourceSerializer`` used to do automatically,
    so passing the raw string straight through to a ``DateTime`` column
    isn't a no-op like it was there: SQLAlchemy's SQLite dialect raises
    ``TypeError: SQLite DateTime type only accepts Python datetime and date
    objects as input`` at flush time. Caught by actually inserting a row in
    a throwaway in-memory DB, not by inspection.
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
            time=datetime.fromisoformat(data["time"]),
        )
        db_session.add(datasource)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=400, detail=str(e)) from e


@post(["/datasources/", "/datasources/kafka"], tags=["datasources"])
async def create_datasource(data: dict[str, Any], db_session: AsyncSession) -> None:
    await _create_datasource(data, db_session)


router = Router(
    path="/",
    route_handlers=[list_datasources, create_datasource],
)
