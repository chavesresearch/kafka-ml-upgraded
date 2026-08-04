"""CASE=2 (SingleIncrementalTraining, TensorFlow) - real API + real Kafka.

Same shape as CASE=1, but the deployment is `incremental=True` and data is
sent via `OnlineRawSink` (the streaming/online sink) in two bursts, since
the training container's streaming Kafka consumer only sees data produced
*after* it joins its consumer group.
"""

import time
import uuid

import numpy as np
from kafkaml_datasources import OnlineRawSink

from common import (
    BOOTSTRAP_SERVERS,
    TF_SINGLE_MODEL_CODE,
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


def test_case2_single_incremental_training():
    run_id = uuid.uuid4().hex[:8]

    with api_client() as client:
        model_id = create_model(client, f"it-case2-model-{run_id}", TF_SINGLE_MODEL_CODE, framework="tf")
        config_id = create_configuration(client, f"it-case2-config-{run_id}", [model_id])
        deployment_id = create_deployment(
            client,
            configuration=config_id,
            batch=4,
            tf_kwargs_fit="epochs=1",
            tf_kwargs_val="",
            incremental=True,
            indefinite=False,
            stream_timeout=30000,
            monitoring_metric="loss",
            change="down",
            improvement=0.05,
            federated=False,
            conf_mat_settings=False,
        )

        # Give the training pod time to start, join its Kafka consumer
        # group, and begin polling before any data is produced - a
        # streaming consumer group with no committed offset starts from
        # "latest", so data produced before it joins would be silently
        # skipped (see model_training/tensorflow/CLAUDE.md's
        # CASE=2 section for the same gotcha in manual testing).
        time.sleep(15)

        topic = f"it-case2-data-{run_id}"
        sink = OnlineRawSink(
            boostrap_servers=BOOTSTRAP_SERVERS,
            topic=topic,
            deployment_id=deployment_id,
            description="integration-test-case2",
            validation_rate=0.2,
        )
        rng = np.random.default_rng(2)
        _send_burst(sink, rng, 10)
        time.sleep(10)
        _send_burst(sink, rng, 10)

        results = wait_for_status(client, deployment_id, "finished", timeout_s=90)

        assert len(results) == 1
        result = results[0]
        assert result["train_metrics"], "expected non-empty train_metrics"
        print(f"CASE=2 OK - deployment {deployment_id}, result {result['id']}: {result['train_metrics']}")


if __name__ == "__main__":
    test_case2_single_incremental_training()
