"""CASE=7 (DistributedFederatedTraining, TensorFlow) - real MNIST, 5 real
local epochs per round, across 5 real aggregation rounds, distributed
father/child pair.

Same father/child pair as CASE=3, `federated=True` + `agg_rounds=5` like
CASE=5. As in test_case7_federated_distributed.py, federated_backend's
collision matcher requires the datasource's declared shape to match the
*edge* (leaf) submodel's own input shape, not the cloud model's.
"""

import uuid

from kafkaml_datasources import FederatedRawSink

from common import BOOTSTRAP_SERVERS, api_client, create_configuration, create_deployment, create_model, wait_for_status
from mnist_common import (
    MNIST_CLOUD_MODEL_CODE,
    MNIST_EDGE_MODEL_CODE,
    epoch_progress_lines,
    kubectl_logs,
    kubectl_pod_names,
    load_mnist_train_subset,
    new_pods,
)

N_TRAIN = 600
EPOCHS = 5
AGG_ROUNDS = 5


def run():
    run_id = uuid.uuid4().hex[:8]
    x, y = load_mnist_train_subset(N_TRAIN, seed=7)
    print(f"CASE=7: loaded {len(x)} real MNIST train images")

    before_pods = kubectl_pod_names()

    with api_client() as client:
        cloud_model_id = create_model(
            client, f"mnist-case7-cloud-{run_id}", MNIST_CLOUD_MODEL_CODE, framework="tf", distributed=True
        )
        edge_model_id = create_model(
            client,
            f"mnist-case7-edge-{run_id}",
            MNIST_EDGE_MODEL_CODE,
            framework="tf",
            distributed=True,
            father=cloud_model_id,
        )
        config_id = create_configuration(client, f"mnist-case7-config-{run_id}", [cloud_model_id])
        deployment_id = create_deployment(
            client,
            configuration=config_id,
            batch=32,
            tf_kwargs_fit=f"epochs={EPOCHS}",
            tf_kwargs_val="",
            incremental=False,
            federated=True,
            agg_rounds=AGG_ROUNDS,
            min_data=100,
            agg_strategy="FedAvg",
            data_restriction={},
            optimizer="adam",
            learning_rate=0.001,
            loss="sparse_categorical_crossentropy",
            metrics="accuracy",
            conf_mat_settings=False,
        )
        print(f"CASE=7: deployment {deployment_id} created (cloud={cloud_model_id}, edge={edge_model_id})")

        topic = f"mnist-case7-data-{run_id}"
        sink = FederatedRawSink(
            boostrap_servers=BOOTSTRAP_SERVERS,
            topic=topic,
            deployment_id=deployment_id,
            description="mnist-case7",
            validation_rate=0.15,
            test_rate=0.1,
        )
        for xi, yi in zip(x, y):
            sink.send(data=xi, label=yi)
        sink.close()
        print("CASE=7: all MNIST data sent, waiting for 5 federated rounds to finish...")

        results = wait_for_status(client, deployment_id, "finished", timeout_s=900, min_results=2)
        assert len(results) == 2, f"expected 2 results, got {len(results)}"

        pods = new_pods(before_pods)
        print(f"CASE=7: new pods since deployment: {pods}")
        epoch_lines = []
        for p in pods:
            epoch_lines += epoch_progress_lines(kubectl_logs(p))
        distinct_epochs = sorted({e for e, _ in epoch_lines})
        print(f"CASE=7: distinct 'Epoch N/M' lines: {distinct_epochs} (total occurrences: {len(epoch_lines)})")

        for r in results:
            print(f"CASE=7: result {r['id']} train_metrics={r['train_metrics']}")

        return {
            "case": 7,
            "deployment_id": deployment_id,
            "results": [{"id": r["id"], "train_metrics": r["train_metrics"]} for r in results],
            "distinct_epochs_in_logs": distinct_epochs,
            "total_epoch_lines": len(epoch_lines),
            "edge_model_id": edge_model_id,
            "cloud_model_id": cloud_model_id,
        }


if __name__ == "__main__":
    import json
    print(json.dumps(run(), indent=2))
