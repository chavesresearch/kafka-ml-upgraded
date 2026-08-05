from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ModelSource(Base):
    """A machine learning model registered for federated training,
    waiting for a compatible Datasource to be matched against.

    ``data_restriction`` is a JSON-encoded *string*, not a native JSON
    column - the real wire format (federated_backend/automl/views.py's
    ``check_colission()``, ported unchanged in app/matching.py) always
    ``json.loads()`` it, and every real client (the main trainer's
    ``DATA_RESTRICTION`` env var, ``FederatedRawSink``) sends it that way.
    ``blockchain`` *is* a genuine native JSON object - it comes from the
    main trainer's own request body as a nested dict, not a sub-string,
    and matching code does real dict access on it
    (``model_item['blockchain']['rpc_url']``), not ``json.loads()``.
    """

    __tablename__ = "model_source"

    id: Mapped[int] = mapped_column(primary_key=True)
    federated_string_id: Mapped[str] = mapped_column(Text)

    input_shape: Mapped[str] = mapped_column(Text)
    output_shape: Mapped[str] = mapped_column(Text)

    data_restriction: Mapped[str] = mapped_column(Text)
    min_data: Mapped[int] = mapped_column(Integer)

    framework: Mapped[str] = mapped_column(Text, default="tf")
    distributed: Mapped[bool] = mapped_column(Boolean, default=False)
    blockchain: Mapped[dict] = mapped_column(JSON, default=dict)

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Datasource(Base):
    """A real Kafka data stream, ready to train a matching ModelSource."""

    __tablename__ = "datasource"

    id: Mapped[int] = mapped_column(primary_key=True)

    input_format: Mapped[str] = mapped_column(Text, default="RAW")
    # JSON-encoded string (see ModelSource.data_restriction's docstring for
    # why) - always json.loads()'d by app/matching.py, never a native
    # JSON column.
    input_config: Mapped[str] = mapped_column(Text, default="")

    incremental: Mapped[bool] = mapped_column(Boolean, default=False)

    topic: Mapped[str] = mapped_column(Text)
    unsupervised_topic: Mapped[str | None] = mapped_column(Text, nullable=True)

    total_msg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    validation_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    test_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    description: Mapped[str] = mapped_column(Text, default="")
    # JSON-encoded string, same reasoning as ModelSource.data_restriction.
    dataset_restrictions: Mapped[str] = mapped_column(Text, default="{}")

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
