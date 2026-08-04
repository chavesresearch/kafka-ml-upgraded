"""CASE=7 (DistributedFederatedTraining, TensorFlow) - real API + real
Kafka + real federated-module round.

Same father/child distributed model pair as CASE=3, but the deployment is
`federated=True` too. federated_backend's collision matcher requires the
datasource's declared shape to match the main trainer's registered
`model.input_shape` exactly - confirmed empirically (not assumed) that
for a distributed chain this is the *edge* (leaf) submodel's own input
shape (`TF_EDGE_MODEL_CODE`'s `edge_input`, shape (1,)), not the cloud
model's - same scalar-per-message convention CASE=3 already uses, the
"batch" deployment field is what groups raw messages into the cloud
model's actual 4-feature input downstream.
"""

import uuid

import numpy as np
from kafkaml_datasources import FederatedRawSink

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


def test_case7_federated_distributed_training():
    run_id = uuid.uuid4().hex[:8]

    with api_client() as client:
        cloud_model_id = create_model(
            client, f"it-case7-cloud-{run_id}", TF_CLOUD_MODEL_CODE, framework="tf", distributed=True
        )
        edge_model_id = create_model(
            client,
            f"it-case7-edge-{run_id}",
            TF_EDGE_MODEL_CODE,
            framework="tf",
            distributed=True,
            father=cloud_model_id,
        )
        config_id = create_configuration(client, f"it-case7-config-{run_id}", [cloud_model_id])

        deployment_id = create_deployment(
            client,
            configuration=config_id,
            batch=4,
            tf_kwargs_fit="epochs=1",
            tf_kwargs_val="",
            incremental=False,
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

        topic = f"it-case7-data-{run_id}"
        sink = FederatedRawSink(
            boostrap_servers=BOOTSTRAP_SERVERS,
            topic=topic,
            deployment_id=deployment_id,
            description="integration-test-case7",
            validation_rate=0.2,
            test_rate=0.1,
        )
        rng = np.random.default_rng(7)
        for _ in range(40):
            x = rng.random(1).astype(np.float32)
            y = np.array([int(x[0] > 0.5)], dtype=np.uint8)
            sink.send(x, y)
        sink.close()

        results = wait_for_status(client, deployment_id, "finished", timeout_s=180, min_results=2)

        assert len(results) == 2, f"expected 2 results (one per submodel), got {len(results)}"
        for result in results:
            assert result["train_metrics"], f"expected non-empty train_metrics for result {result['id']}"
        print(f"CASE=7 OK - deployment {deployment_id}, results: {[(r['id'], r['train_metrics']) for r in results]}")


if __name__ == "__main__":
    test_case7_federated_distributed_training()
