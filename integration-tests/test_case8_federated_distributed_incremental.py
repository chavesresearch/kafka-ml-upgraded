"""CASE=8 (DistributedFederatedIncrementalTraining, TensorFlow) - real API
+ real Kafka + real federated-module round.

Combines CASE=6 (federated + incremental, so data goes through
`OnlineFederatedRawSink` continuously - see CASE=6's comment for why a
flat pre-sleep doesn't work) and CASE=7 (distributed father/child model
pair - shape (1,) data, matching the *edge* submodel's own input shape,
confirmed empirically the same way CASE=7's own comment explains).
"""

import time
import uuid

import numpy as np
from kafkaml_datasources import OnlineFederatedRawSink

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


def _send_burst(sink: OnlineFederatedRawSink, rng: np.random.Generator, n: int) -> None:
    for _ in range(n):
        x = rng.random(1).astype(np.float32)
        y = np.array([int(x[0] > 0.5)], dtype=np.uint8)
        sink.send(x, y)


def test_case8_federated_distributed_incremental_training():
    run_id = uuid.uuid4().hex[:8]

    with api_client() as client:
        cloud_model_id = create_model(
            client, f"it-case8-cloud-{run_id}", TF_CLOUD_MODEL_CODE, framework="tf", distributed=True
        )
        edge_model_id = create_model(
            client,
            f"it-case8-edge-{run_id}",
            TF_EDGE_MODEL_CODE,
            framework="tf",
            distributed=True,
            father=cloud_model_id,
        )
        config_id = create_configuration(client, f"it-case8-config-{run_id}", [cloud_model_id])

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
            optimizer="adam",
            learning_rate=0.001,
            loss="sparse_categorical_crossentropy",
            metrics="accuracy",
            conf_mat_settings=False,
        )

        topic = f"it-case8-data-{run_id}"
        sink = OnlineFederatedRawSink(
            boostrap_servers=BOOTSTRAP_SERVERS,
            topic=topic,
            deployment_id=deployment_id,
            description="integration-test-case8",
            validation_rate=0.2,
        )
        rng = np.random.default_rng(8)
        x0 = rng.random(1).astype(np.float32)
        y0 = np.array([int(x0[0] > 0.5)], dtype=np.uint8)
        sink.send_online_control_msg(x0, y0)

        # See test_case6_federated_incremental.py's comment: the edge
        # Job's startup latency isn't predictable enough for one flat
        # pre-sleep, so send a steady trickle for a long window instead -
        # whenever the edge worker actually joins, fresh data is flowing.
        for _ in range(30):
            _send_burst(sink, rng, 2)
            time.sleep(3)

        results = wait_for_status(client, deployment_id, "finished", timeout_s=180, min_results=2)

        assert len(results) == 2, f"expected 2 results (one per submodel), got {len(results)}"
        for result in results:
            assert result["train_metrics"], f"expected non-empty train_metrics for result {result['id']}"
        print(f"CASE=8 OK - deployment {deployment_id}, results: {[(r['id'], r['train_metrics']) for r in results]}")


if __name__ == "__main__":
    test_case8_federated_distributed_incremental_training()
