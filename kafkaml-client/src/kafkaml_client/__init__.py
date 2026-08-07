"""A Python client for the Kafka-ML backend REST API.

Wraps the same endpoints the frontend calls (``POST /models/``,
``/configurations/``, ``/deployments/``, ``/results/``,
``/results/inference/{id}``, ...) behind a small, typed-ish Python
surface, so a script or notebook can drive Kafka-ML without hand-rolling
`httpx`/`requests` calls and remembering each endpoint's exact field
names.

    from kafkaml_client import KafkaMLClient

    client = KafkaMLClient("http://localhost:8000")
    model_id = client.create_model(name="my-model", code=MODEL_CODE, framework="tf")
    config_id = client.create_configuration(name="my-config", model_ids=[model_id])
    deployment_id = client.create_deployment(
        configuration=config_id, batch=4, tf_kwargs_fit="epochs=1",
    )
    # Sends a numpy/pandas dataset to Kafka and registers it as a
    # datasource for this deployment - needs the 'datasets' extra
    # (`pip install kafkaml-client[datasets]`); see kafkaml_client.datasets.
    client.send_dataset("localhost:9094", topic="my-topic", deployment_id=deployment_id, data=X, labels=y)
    results = client.wait_for_results(deployment_id, timeout=120)
"""

from .client import KafkaMLClient, KafkaMLError

__all__ = ["KafkaMLClient", "KafkaMLError"]
