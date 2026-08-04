"""CASE=6 (SingleFederatedIncrementalTraining, TensorFlow) - real API +
real Kafka + real federated-module round.

Same shape as CASE=5, but the deployment is `incremental=True` too and
data is sent via `OnlineFederatedRawSink` (the streaming/online federated
sink) in two bursts, same reasoning as CASE=2 - the edge worker's
streaming Kafka consumer only sees data produced *after* it joins its
consumer group.
"""

import time
import uuid

import numpy as np
from kafkaml_datasources import OnlineFederatedRawSink

from common import (
    BOOTSTRAP_SERVERS,
    TF_SINGLE_MODEL_CODE,
    api_client,
    create_configuration,
    create_deployment,
    create_model,
    wait_for_status,
)


def _send_burst(sink: OnlineFederatedRawSink, rng: np.random.Generator, n: int) -> None:
    for _ in range(n):
        x = rng.random(1).astype(np.float32)
        y = np.array([int(x[0] > 0.5)], dtype=np.uint8)
        sink.send(x, y)


def test_case6_federated_incremental_training():
    run_id = uuid.uuid4().hex[:8]

    with api_client() as client:
        model_id = create_model(client, f"it-case6-model-{run_id}", TF_SINGLE_MODEL_CODE, framework="tf")
        config_id = create_configuration(client, f"it-case6-config-{run_id}", [model_id])
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
            federated=True,
            agg_rounds=1,
            min_data=5,
            agg_strategy="FedAvg",
            data_restriction={},
            conf_mat_settings=False,
        )

        # Unlike CASE=2 (the trainer pod already exists and is already
        # polling before any data shows up), the federated edge worker
        # Job doesn't even get *created* until federated_backend's
        # collision matcher sees both this datasource registration *and*
        # the main trainer's own model registration (which depends on the
        # main trainer's own pod scheduling/TF-import/pre-model-download
        # time - not under this script's control) - then the edge Job
        # itself needs to schedule, boot, import TF, and join its Kafka
        # consumer group. That whole chain's latency isn't fixed enough to
        # bet on a single pre-send sleep - confirmed empirically: one
        # attempt with a 45s flat pre-sleep still missed the window
        # (edge worker joined at offset 0, correctly, but its 30s
        # stream_timeout had already elapsed with zero messages by the
        # time this script's sleep(45) ended and .send() finally ran).
        # Fix: send a steady trickle for a long total window instead of
        # betting on one timing guess - whenever the edge worker actually
        # joins, fresh data is already flowing, and each message resets
        # its idle timer (same mechanism CASE=2 relies on between its two
        # bursts, just stretched over a longer, denser window here).
        topic = f"it-case6-data-{run_id}"
        sink = OnlineFederatedRawSink(
            boostrap_servers=BOOTSTRAP_SERVERS,
            topic=topic,
            deployment_id=deployment_id,
            description="integration-test-case6",
            validation_rate=0.2,
        )
        rng = np.random.default_rng(6)
        x0 = rng.random(1).astype(np.float32)
        y0 = np.array([int(x0[0] > 0.5)], dtype=np.uint8)
        sink.send_online_control_msg(x0, y0)

        for _ in range(30):
            _send_burst(sink, rng, 2)
            time.sleep(3)

        results = wait_for_status(client, deployment_id, "finished", timeout_s=180)

        assert len(results) == 1
        result = results[0]
        assert result["train_metrics"], "expected non-empty train_metrics"
        print(f"CASE=6 OK - deployment {deployment_id}, result {result['id']}: {result['train_metrics']}")


if __name__ == "__main__":
    test_case6_federated_incremental_training()
