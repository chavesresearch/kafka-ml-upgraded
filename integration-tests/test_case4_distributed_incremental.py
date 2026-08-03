"""CASE=4 (DistributedIncrementalTraining, TensorFlow) - real API + real Kafka.

Combines CASE=2 (incremental, `OnlineRawSink`, two bursts) and CASE=3
(distributed father/child model pair) - the one path where the training
container's streaming consumer group id is a Python list (one id per
submodel), stringified for Kafka's wire protocol.
"""

import time
import uuid

import numpy as np
from kafkaml_datasources import OnlineRawSink

from common import (
    BOOTSTRAP_SERVERS,
    TF_CLOUD_MODEL_CODE,
    TF_EDGE_MODEL_CODE,
    api_client,
    create_configuration,
    create_deployment,
    create_model,
    wait_for_status,
)


def _send_burst(sink: OnlineRawSink, rng: np.random.Generator, n: int) -> None:
    for _ in range(n):
        x = rng.random(1).astype(np.float32)
        y = np.array([int(x[0] > 0.5)], dtype=np.uint8)
        sink.send(x, y)


def test_case4_distributed_incremental_training():
    run_id = uuid.uuid4().hex[:8]

    with api_client() as client:
        cloud_model_id = create_model(
            client, f"it-case4-cloud-{run_id}", TF_CLOUD_MODEL_CODE, framework="tf", distributed=True
        )
        edge_model_id = create_model(
            client,
            f"it-case4-edge-{run_id}",
            TF_EDGE_MODEL_CODE,
            framework="tf",
            distributed=True,
            father=cloud_model_id,
        )
        config_id = create_configuration(client, f"it-case4-config-{run_id}", [cloud_model_id])

        deployment_id = create_deployment(
            client,
            configuration=config_id,
            batch=4,
            tf_kwargs_fit="epochs=1",
            tf_kwargs_val="",
            incremental=True,
            indefinite=False,
            stream_timeout=45000,
            monitoring_metric="loss",
            change="down",
            improvement=0.05,
            federated=False,
            optimizer="adam",
            learning_rate=0.001,
            loss="sparse_categorical_crossentropy",
            metrics="accuracy",
            conf_mat_settings=False,
        )

        # Distributed + incremental has more startup work than the single
        # non-distributed case (two model downloads, building the combined
        # multi-output graph) before the streaming Kafka consumer group
        # actually joins - a fixed 15s (enough for CASE=2's single-model
        # case) wasn't enough here in practice (observed the consumer
        # resetting to the *end* offset, having missed both bursts
        # entirely). Generous margin instead of a tighter timing-dependent
        # wait.
        time.sleep(35)

        topic = f"it-case4-data-{run_id}"
        sink = OnlineRawSink(
            boostrap_servers=BOOTSTRAP_SERVERS,
            topic=topic,
            deployment_id=deployment_id,
            description="integration-test-case4",
            validation_rate=0.2,
        )
        rng = np.random.default_rng(4)
        _send_burst(sink, rng, 10)
        time.sleep(10)
        _send_burst(sink, rng, 10)

        results = wait_for_status(client, deployment_id, "finished", timeout_s=90, min_results=2)

        assert len(results) == 2, f"expected 2 results (one per submodel), got {len(results)}"
        print(f"CASE=4 OK - deployment {deployment_id}, results: {[(r['id'], r['train_metrics']) for r in results]}")


if __name__ == "__main__":
    test_case4_distributed_incremental_training()
