"""CASE=2 (SingleIncrementalTraining, TensorFlow) - real API + real Kafka.

Same shape as CASE=1, but the deployment is `incremental=True` and data is
sent via `OnlineRawSink` (the streaming/online sink) in two bursts, since
the training container's streaming Kafka consumer only sees data produced
*after* it joins its consumer group.

The pre-sink `time.sleep()` this test used to rely on to protect that join
doesn't actually work: `OnlineRawSink.send()` only fires the online
control message (the signal the trainer needs before it'll even start
joining the *data* topic's consumer group) as a side effect of its own
*first* call - so no amount of waiting before creating the sink helps, and
the tight, delay-free burst loop routinely finished sending before the
trainer's consumer group join round-trip completed, silently dropping
that burst (see FUTURE.md High #7 for the full incident this caused: a
UnboundLocalError crash in the pre-fix trainer code, later fixed in
model_training/tensorflow/mainTraining.py's train_incremental_model).
Fixed here the deterministic way instead of guessing a "long enough"
margin: pre-configure the sink's format explicitly (skips the
auto-detect-on-first-send path) and call the public
`send_online_control_msg()` directly, *then* wait, *then* send real data -
same pattern already noted as more reliable in
model_training/tensorflow/CLAUDE.md's CASE=2 section.
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

        topic = f"it-case2-data-{run_id}"
        # data_type/label_type/data_reshape/label_reshape match what
        # send()'s own auto-detect would derive for a (1,) float32/uint8
        # pair - passing them explicitly marks the sink "already
        # configured" so the *first* send() below doesn't also fire the
        # control message (send_online_control_msg() below already did).
        sink = OnlineRawSink(
            boostrap_servers=BOOTSTRAP_SERVERS,
            topic=topic,
            deployment_id=deployment_id,
            description="integration-test-case2",
            validation_rate=0.2,
            data_type="float32",
            label_type="uint8",
            data_reshape="1",
            label_reshape="1",
        )
        sink.send_online_control_msg()

        # Now wait for the training pod to start, receive that control
        # message, and join its Kafka consumer group before any real data
        # is produced - a streaming consumer group with no committed
        # offset starts from "latest", so data produced before it joins
        # would be silently skipped.
        time.sleep(15)

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
