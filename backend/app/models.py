import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Table,
    Column,
    Text,
    event,
)
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Mapped, mapped_column, relationship, Session

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def generate_unique_token() -> str:
    return str(uuid.uuid4())[:8].upper()


configuration_ml_models = Table(
    "configuration_ml_models",
    Base.metadata,
    Column("configuration_id", ForeignKey("configuration.id", ondelete="CASCADE"), primary_key=True),
    Column("ml_model_id", ForeignKey("ml_model.id", ondelete="CASCADE"), primary_key=True),
)


class MLModel(Base):
    """Machine learning model to be trained in the system."""

    __tablename__ = "ml_model"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(30), unique=True)
    description: Mapped[str] = mapped_column(String(100), default="")
    imports: Mapped[str] = mapped_column(Text, default="")
    code: Mapped[str] = mapped_column(Text)
    distributed: Mapped[bool] = mapped_column(Boolean, default=False)
    father_id: Mapped[int | None] = mapped_column(
        ForeignKey("ml_model.id", ondelete="SET NULL"), unique=True, nullable=True
    )
    framework: Mapped[str] = mapped_column(Text)

    father: Mapped["MLModel | None"] = relationship(
        remote_side=[id], back_populates="child", foreign_keys=[father_id]
    )
    child: Mapped["MLModel | None"] = relationship(
        back_populates="father", uselist=False, foreign_keys=[father_id]
    )

    configurations: Mapped[list["Configuration"]] = relationship(
        secondary=configuration_ml_models, back_populates="ml_models"
    )
    trained: Mapped[list["TrainingResult"]] = relationship(
        back_populates="model", cascade="all, delete-orphan", passive_deletes=True
    )


class Configuration(Base):
    """Set of ML models to be used for training."""

    __tablename__ = "configuration"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(30), unique=True)
    description: Mapped[str] = mapped_column(String(100), default="")
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    ml_models: Mapped[list[MLModel]] = relationship(
        secondary=configuration_ml_models, back_populates="configurations"
    )
    deployments: Mapped[list["Deployment"]] = relationship(
        back_populates="configuration", cascade="all, delete-orphan", passive_deletes=True
    )


AGGREGATION_STRATEGIES = ("FedAvg", "FedOpt", "FedAdagrad", "FedAdam", "FedYogi")


class Deployment(Base):
    """Deployment of a configuration of models for training."""

    __tablename__ = "deployment"

    id: Mapped[int] = mapped_column(primary_key=True)

    # General deployment settings
    batch: Mapped[int] = mapped_column(Integer, default=1)
    tf_kwargs_fit: Mapped[str] = mapped_column(String(100), default="")
    tf_kwargs_val: Mapped[str] = mapped_column(String(100), default="")
    pth_kwargs_fit: Mapped[str] = mapped_column(String(100), default="")
    pth_kwargs_val: Mapped[str] = mapped_column(String(100), default="")
    conf_mat_settings: Mapped[bool | None] = mapped_column(Boolean, default=False)
    configuration_id: Mapped[int] = mapped_column(
        ForeignKey("configuration.id", ondelete="CASCADE")
    )
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Distributed deployment settings
    optimizer: Mapped[str] = mapped_column(Text, default="adam")
    learning_rate: Mapped[float] = mapped_column(default=0.001)
    loss: Mapped[str] = mapped_column(Text, default="sparse_categorical_crossentropy")
    metrics: Mapped[str] = mapped_column(Text, default="sparse_categorical_accuracy")

    # Incremental deployment settings
    incremental: Mapped[bool] = mapped_column(Boolean, default=False)
    indefinite: Mapped[bool] = mapped_column(Boolean, default=False)
    stream_timeout: Mapped[int | None] = mapped_column(Integer, default=60000)
    monitoring_metric: Mapped[str | None] = mapped_column(Text, default=None)
    change: Mapped[str | None] = mapped_column(Text, default=None)
    improvement: Mapped[float | None] = mapped_column(default=0.05)

    # Unsupervised deployment settings
    unsupervised: Mapped[bool] = mapped_column(Boolean, default=False)
    unsupervised_rounds: Mapped[int | None] = mapped_column(Integer, default=5)
    confidence: Mapped[float | None] = mapped_column(default=0.9)

    # Federated deployment settings
    federated: Mapped[bool] = mapped_column(Boolean, default=False)
    agg_rounds: Mapped[int | None] = mapped_column(Integer, default=15)
    min_data: Mapped[int | None] = mapped_column(Integer, default=1000)
    agg_strategy: Mapped[str] = mapped_column(String(20), default=AGGREGATION_STRATEGIES[0])
    data_restriction: Mapped[dict] = mapped_column(JSON, default=dict)

    # Federated blockchain deployment settings
    blockchain: Mapped[bool] = mapped_column(Boolean, default=False)

    configuration: Mapped[Configuration] = relationship(back_populates="deployments")
    results: Mapped[list["TrainingResult"]] = relationship(
        back_populates="deployment", cascade="all, delete-orphan", passive_deletes=True
    )


TRAINING_RESULT_STATUS = ("created", "deployed", "stopped", "finished")


class TrainingResult(Base):
    """Training result information obtained once deployed a model."""

    __tablename__ = "training_result"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default=TRAINING_RESULT_STATUS[0])
    status_changed: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deployment_id: Mapped[int] = mapped_column(ForeignKey("deployment.id", ondelete="CASCADE"))
    model_id: Mapped[int] = mapped_column(ForeignKey("ml_model.id", ondelete="CASCADE"))
    train_metrics: Mapped[dict | list | None] = mapped_column(JSON, default=None)
    val_metrics: Mapped[dict | list | None] = mapped_column(JSON, default=None)
    test_metrics: Mapped[dict | list | None] = mapped_column(JSON, default=None)
    confusion_matrix: Mapped[dict | list | None] = mapped_column(JSON, default=None)
    training_time: Mapped[float | None] = mapped_column(default=None)
    trained_model_path: Mapped[str] = mapped_column(String(255), default="")
    confusion_mat_img_path: Mapped[str | None] = mapped_column(String(255), default=None)

    deployment: Mapped[Deployment] = relationship(back_populates="results")
    model: Mapped[MLModel] = relationship(back_populates="trained")
    inferences: Mapped[list["Inference"]] = relationship(back_populates="model_result")


class Datasource(Base):
    """Datasource used for training a deployed model."""

    __tablename__ = "datasource"

    id: Mapped[int] = mapped_column(primary_key=True)
    input_format: Mapped[str] = mapped_column(String(20), default="RAW")
    deployment: Mapped[str] = mapped_column(Text)
    input_config: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    topic: Mapped[str] = mapped_column(Text)
    total_msg: Mapped[int | None] = mapped_column(Integer, default=None)
    validation_rate: Mapped[float | None] = mapped_column(default=None)
    test_rate: Mapped[float | None] = mapped_column(default=None)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True))


INFERENCE_STATUS = ("deployed", "stopped")


class Inference(Base):
    """Inference deployment obtained once a training result exists."""

    __tablename__ = "inference"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default=INFERENCE_STATUS[0])
    status_changed: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    model_result_id: Mapped[int | None] = mapped_column(
        ForeignKey("training_result.id", ondelete="SET NULL"), nullable=True
    )
    replicas: Mapped[int] = mapped_column(Integer, default=1)
    input_format: Mapped[str] = mapped_column(String(20), default="RAW")
    input_config: Mapped[str] = mapped_column(Text, default="")
    input_topic: Mapped[str] = mapped_column(Text, default="")
    output_topic: Mapped[str] = mapped_column(Text, default="")
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    limit: Mapped[float | None] = mapped_column(default=None)
    output_upper: Mapped[str] = mapped_column(Text, default="")
    token: Mapped[str | None] = mapped_column(Text, default=None)
    external_host: Mapped[str | None] = mapped_column(Text, default=None)
    input_kafka_broker: Mapped[str | None] = mapped_column(Text, default=None)
    output_kafka_broker: Mapped[str | None] = mapped_column(Text, default=None)
    upper_kafka_broker: Mapped[str | None] = mapped_column(Text, default=None)

    model_result: Mapped[TrainingResult | None] = relationship(back_populates="inferences")


class IoTDevice(Base):
    """IoT device to be used for training/inference on the edge."""

    __tablename__ = "iot_device"

    id: Mapped[int] = mapped_column(primary_key=True)
    friendly_name: Mapped[str] = mapped_column(String(30), unique=True)
    token: Mapped[str] = mapped_column(String(8), unique=True, default=generate_unique_token)
    mqtt_address: Mapped[str] = mapped_column(Text)
    mqtt_port: Mapped[int] = mapped_column(Integer)
    mqtt_username: Mapped[str] = mapped_column(Text)
    # WARNING: stored in plain text, same as the original Django model. Should
    # be encrypted at rest before any real production use.
    mqtt_password: Mapped[str] = mapped_column(Text)


@event.listens_for(Session, "before_flush")
def _touch_status_changed(session: Session, flush_context, instances) -> None:
    """Reproduces django-model-utils' MonitorField: whenever ``status`` changes
    on a dirty TrainingResult/Inference, bump ``status_changed`` to now."""
    for obj in session.dirty:
        if not isinstance(obj, (TrainingResult, Inference)):
            continue
        if sa_inspect(obj).attrs.status.history.has_changes():
            obj.status_changed = utcnow()
