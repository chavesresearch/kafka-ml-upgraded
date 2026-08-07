"""Response dict builders.

These mirror the field lists of the original DRF ``ModelSerializer`` classes
(``automl/serializers.py``) one-for-one, so the JSON shape returned to the
Angular frontend is unchanged. Kept as plain functions (rather than a DTO/
serializer class hierarchy) since none of them need bidirectional
(de)serialization - request-body validation is handled separately, in each
controller, against plain dicts.
"""

from typing import Any

from app.models import (
    Configuration,
    Datasource,
    Deployment,
    IoTDevice,
    Inference,
    MLModel,
    TrainingResult,
)


def simple_model_dict(model: MLModel | None) -> dict[str, Any] | None:
    if model is None:
        return None
    return {"id": model.id, "name": model.name, "framework": model.framework}


def model_dict(model: MLModel) -> dict[str, Any]:
    return {
        "id": model.id,
        "code": model.code,
        "name": model.name,
        "description": model.description,
        "imports": model.imports,
        "distributed": model.distributed,
        "father": simple_model_dict(model.father),
        "framework": model.framework,
        "created_at": model.created_at,
        "updated_at": model.updated_at,
    }


def simple_deployment_dict(deployment: Deployment) -> dict[str, Any]:
    return {"id": deployment.id, "time": deployment.time}


def simple_configuration_dict(configuration: Configuration) -> dict[str, Any]:
    return {"id": configuration.id, "name": configuration.name}


def simple_training_result_dict(result: TrainingResult) -> dict[str, Any]:
    return {
        "id": result.id,
        "status": result.status,
        "model": simple_model_dict(result.model),
        "status_changed": result.status_changed,
    }


def configuration_dict(configuration: Configuration) -> dict[str, Any]:
    return {
        "id": configuration.id,
        "name": configuration.name,
        "description": configuration.description,
        "ml_models": [simple_model_dict(m) for m in configuration.ml_models],
        "deployments": [simple_deployment_dict(d) for d in configuration.deployments],
    }


_DEPLOYMENT_SETTING_FIELDS = (
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
    "tf_kwargs_fit",
    "tf_kwargs_val",
    "pth_kwargs_fit",
    "pth_kwargs_val",
    "conf_mat_settings",
    "federated",
    "agg_rounds",
    "min_data",
    "agg_strategy",
    "data_restriction",
    "blockchain",
)


def deployment_dict(deployment: Deployment) -> dict[str, Any]:
    data: dict[str, Any] = {"id": deployment.id}
    for field in _DEPLOYMENT_SETTING_FIELDS:
        data[field] = getattr(deployment, field)
    data["configuration"] = simple_configuration_dict(deployment.configuration)
    data["results"] = [simple_training_result_dict(r) for r in deployment.results]
    data["time"] = deployment.time
    return data


def training_result_dict(result: TrainingResult) -> dict[str, Any]:
    return {
        "id": result.id,
        "status": result.status,
        "status_changed": result.status_changed,
        "deployment": simple_deployment_dict(result.deployment),
        "model": simple_model_dict(result.model),
        "train_metrics": result.train_metrics,
        "val_metrics": result.val_metrics,
        "test_metrics": result.test_metrics,
        "confusion_matrix": result.confusion_matrix,
        "training_time": result.training_time,
    }


def simple_result_dict(result: TrainingResult) -> dict[str, Any]:
    return {
        "id": result.id,
        "train_metrics": result.train_metrics,
        "val_metrics": result.val_metrics,
        "test_metrics": result.test_metrics,
        "confusion_matrix": result.confusion_matrix,
        "training_time": result.training_time,
    }


def simpler_result_dict(result: TrainingResult) -> dict[str, Any]:
    return {
        "id": result.id,
        "train_metrics": result.train_metrics,
        "val_metrics": result.val_metrics,
    }


def datasource_dict(datasource: Datasource) -> dict[str, Any]:
    return {
        "input_format": datasource.input_format,
        "deployment": datasource.deployment,
        "input_config": datasource.input_config,
        "description": datasource.description,
        "topic": datasource.topic,
        "validation_rate": datasource.validation_rate,
        "test_rate": datasource.test_rate,
        "total_msg": datasource.total_msg,
        "time": datasource.time,
    }


def inference_dict(inference: Inference) -> dict[str, Any]:
    return {
        "id": inference.id,
        "model_result": inference.model_result_id,
        "replicas": inference.replicas,
        "input_format": inference.input_format,
        "input_config": inference.input_config,
        "input_topic": inference.input_topic,
        "output_topic": inference.output_topic,
        "time": inference.time,
        "status": inference.status,
        "status_changed": inference.status_changed,
        "limit": inference.limit,
        "output_upper": inference.output_upper,
        # inference.token is a bearer credential for an external Kubernetes
        # cluster (write-only: set at creation, never updated, there is no
        # PUT/PATCH for inferences) - it must never be echoed back over the
        # API. `frontend`'s Inference type doesn't declare this field and
        # nothing reads it; confirmed by grep before removing it.
        "external_host": inference.external_host,
        "input_kafka_broker": inference.input_kafka_broker,
        "output_kafka_broker": inference.output_kafka_broker,
        "upper_kafka_broker": inference.upper_kafka_broker,
    }


def iot_device_dict(device: IoTDevice) -> dict[str, Any]:
    return {
        "id": device.id,
        "friendly_name": device.friendly_name,
        "token": device.token,
        "mqtt_address": device.mqtt_address,
        "mqtt_port": device.mqtt_port,
        "mqtt_username": device.mqtt_username,
        "mqtt_password": device.mqtt_password,
    }
