"""CASE=1 (SingleClassicTraining, TensorFlow) - real API + real Kafka.

Creates a model/configuration/deployment through the real REST API (which
makes backend-litestar submit a real Kubernetes training Job), sends real
RAW-format data via `datasources-package`'s `RawSink`, and waits for the
result to reach `status: "finished"` with real train/val/test metrics.
"""

import uuid

import numpy as np
from kafkaml_datasources import RawSink

from common import (
    BOOTSTRAP_SERVERS,
    TF_SINGLE_MODEL_CODE,
    api_client,
    create_configuration,
    create_deployment,
    create_model,
    wait_for_status,
)


def test_case1_single_classic_training():
    run_id = uuid.uuid4().hex[:8]

    with api_client() as client:
        model_id = create_model(client, f"it-case1-model-{run_id}", TF_SINGLE_MODEL_CODE, framework="tf")
        config_id = create_configuration(client, f"it-case1-config-{run_id}", [model_id])
        deployment_id = create_deployment(
            client,
            configuration=config_id,
            batch=4,
            tf_kwargs_fit="epochs=1",
            tf_kwargs_val="",
            incremental=False,
            federated=False,
            conf_mat_settings=False,
        )

        topic = f"it-case1-data-{run_id}"
        sink = RawSink(
            boostrap_servers=BOOTSTRAP_SERVERS,
            topic=topic,
            deployment_id=deployment_id,
            description="integration-test-case1",
            validation_rate=0.2,
            test_rate=0.1,
        )
        rng = np.random.default_rng(1)
        for _ in range(40):
            x = rng.random(1).astype(np.float32)
            y = np.array([int(x[0] > 0.5)], dtype=np.uint8)
            sink.send(x, y)
        sink.close()

        results = wait_for_status(client, deployment_id, "finished")

        assert len(results) == 1
        result = results[0]
        assert result["train_metrics"], "expected non-empty train_metrics"
        assert "accuracy" in result["train_metrics"]
        assert "loss" in result["train_metrics"]
        print(f"CASE=1 OK - deployment {deployment_id}, result {result['id']}: {result['train_metrics']}")


if __name__ == "__main__":
    test_case1_single_classic_training()
