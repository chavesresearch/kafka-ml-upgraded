"""CASE=5 (SingleFederatedTraining, TensorFlow) - real API + real Kafka +
real federated-module round.

Creates a model/configuration/federated deployment through the real REST
API (backend submits a real main-trainer Kubernetes Job), sends a real
RAW-format datasource via `datasources`'s `FederatedRawSink` (registered
with `federated_backend` via `federated_data_control_logger`), and waits
for the result to reach `status: "finished"`. Requires `federated-module`
(federated_backend, federated_data_control_logger,
federated_model_control_logger) running alongside the base stack - see
README.md's federated prerequisites section.
"""

import uuid

import numpy as np
from kafkaml_datasources import FederatedRawSink

from common import (
    BOOTSTRAP_SERVERS,
    TF_SINGLE_MODEL_CODE,
    api_client,
    create_configuration,
    create_deployment,
    create_model,
    wait_for_status,
)


def test_case5_federated_single_training():
    run_id = uuid.uuid4().hex[:8]

    with api_client() as client:
        model_id = create_model(client, f"it-case5-model-{run_id}", TF_SINGLE_MODEL_CODE, framework="tf")
        config_id = create_configuration(client, f"it-case5-config-{run_id}", [model_id])
        deployment_id = create_deployment(
            client,
            configuration=config_id,
            batch=4,
            tf_kwargs_fit="epochs=1",
            tf_kwargs_val="",
            incremental=False,
            federated=True,
            agg_rounds=1,
            min_data=10,
            agg_strategy="FedAvg",
            data_restriction={},
            conf_mat_settings=False,
        )

        topic = f"it-case5-data-{run_id}"
        sink = FederatedRawSink(
            boostrap_servers=BOOTSTRAP_SERVERS,
            topic=topic,
            deployment_id=deployment_id,
            description="integration-test-case5",
            validation_rate=0.2,
            test_rate=0.1,
        )
        rng = np.random.default_rng(5)
        for _ in range(40):
            x = rng.random(1).astype(np.float32)
            y = np.array([int(x[0] > 0.5)], dtype=np.uint8)
            sink.send(x, y)
        sink.close()

        results = wait_for_status(client, deployment_id, "finished", timeout_s=180)

        assert len(results) == 1
        result = results[0]
        assert result["train_metrics"], "expected non-empty train_metrics"
        print(f"CASE=5 OK - deployment {deployment_id}, result {result['id']}: {result['train_metrics']}")


if __name__ == "__main__":
    test_case5_federated_single_training()
