"""CASE=3 (DistributedClassicTraining, TensorFlow) - real API + real Kafka.

Creates a real father/child distributed model pair through the API
(`father` field on the child model), a configuration built from just the
*root* model id (backend-litestar's `_expand_with_children` walks the
father/child chain automatically), and a deployment with the distributed
optimizer/learning_rate/loss/metrics fields.
"""

import uuid

import numpy as np
from kafkaml_datasources import RawSink

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


def test_case3_distributed_classic_training():
    run_id = uuid.uuid4().hex[:8]

    with api_client() as client:
        cloud_model_id = create_model(
            client, f"it-case3-cloud-{run_id}", TF_CLOUD_MODEL_CODE, framework="tf", distributed=True
        )
        edge_model_id = create_model(
            client,
            f"it-case3-edge-{run_id}",
            TF_EDGE_MODEL_CODE,
            framework="tf",
            distributed=True,
            father=cloud_model_id,
        )
        # Only the root (father-less) model id is needed - the child gets
        # pulled in automatically.
        config_id = create_configuration(client, f"it-case3-config-{run_id}", [cloud_model_id])

        deployment_id = create_deployment(
            client,
            configuration=config_id,
            batch=4,
            tf_kwargs_fit="epochs=1",
            tf_kwargs_val="",
            incremental=False,
            federated=False,
            optimizer="adam",
            learning_rate=0.001,
            loss="sparse_categorical_crossentropy",
            metrics="accuracy",
            conf_mat_settings=False,
        )

        topic = f"it-case3-data-{run_id}"
        sink = RawSink(
            boostrap_servers=BOOTSTRAP_SERVERS,
            topic=topic,
            deployment_id=deployment_id,
            description="integration-test-case3",
            validation_rate=0.2,
            test_rate=0.1,
        )
        rng = np.random.default_rng(3)
        for _ in range(40):
            x = rng.random(1).astype(np.float32)
            y = np.array([int(x[0] > 0.5)], dtype=np.uint8)
            sink.send(x, y)
        sink.close()

        results = wait_for_status(client, deployment_id, "finished", min_results=2)

        assert len(results) == 2, f"expected 2 results (one per submodel), got {len(results)}"
        for result in results:
            assert result["train_metrics"], f"expected non-empty train_metrics for result {result['id']}"
        print(f"CASE=3 OK - deployment {deployment_id}, results: {[(r['id'], r['train_metrics']) for r in results]}")


if __name__ == "__main__":
    test_case3_distributed_classic_training()
