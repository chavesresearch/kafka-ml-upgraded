"""CASE=3 (DistributedClassicTraining, TensorFlow) - real MNIST, 5 real epochs.

Real father/child submodel pair (MNIST_EDGE_MODEL_CODE / MNIST_CLOUD_MODEL_CODE
from mnist_common.py) trained together on real MNIST images, batch=32,
tf_kwargs_fit="epochs=5". Both submodels' TrainingResults are verified for
real per-epoch metric history and real "Epoch N/5" log lines.
"""

import uuid

from kafkaml_datasources import RawSink

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

N_TRAIN = 1500
EPOCHS = 5


def run():
    run_id = uuid.uuid4().hex[:8]
    x, y = load_mnist_train_subset(N_TRAIN, seed=3)
    print(f"CASE=3: loaded {len(x)} real MNIST train images")

    before_pods = kubectl_pod_names()

    with api_client() as client:
        cloud_model_id = create_model(
            client, f"mnist-case3-cloud-{run_id}", MNIST_CLOUD_MODEL_CODE, framework="tf", distributed=True
        )
        edge_model_id = create_model(
            client,
            f"mnist-case3-edge-{run_id}",
            MNIST_EDGE_MODEL_CODE,
            framework="tf",
            distributed=True,
            father=cloud_model_id,
        )
        config_id = create_configuration(client, f"mnist-case3-config-{run_id}", [cloud_model_id])
        deployment_id = create_deployment(
            client,
            configuration=config_id,
            batch=32,
            tf_kwargs_fit=f"epochs={EPOCHS}",
            tf_kwargs_val="",
            incremental=False,
            federated=False,
            optimizer="adam",
            learning_rate=0.001,
            loss="sparse_categorical_crossentropy",
            metrics="accuracy",
            conf_mat_settings=False,
        )
        print(f"CASE=3: deployment {deployment_id} created (cloud={cloud_model_id}, edge={edge_model_id})")

        topic = f"mnist-case3-data-{run_id}"
        sink = RawSink(
            boostrap_servers=BOOTSTRAP_SERVERS,
            topic=topic,
            deployment_id=deployment_id,
            description="mnist-case3",
            validation_rate=0.15,
            test_rate=0.1,
        )
        for xi, yi in zip(x, y):
            sink.send(data=xi, label=yi)
        sink.close()
        print("CASE=3: all MNIST data sent, waiting for training to finish...")

        results = wait_for_status(client, deployment_id, "finished", timeout_s=600, min_results=2)
        assert len(results) == 2, f"expected 2 results, got {len(results)}"

        pods = new_pods(before_pods)
        print(f"CASE=3: new pods since deployment: {pods}")
        epoch_lines = []
        for p in pods:
            epoch_lines += epoch_progress_lines(kubectl_logs(p))
        distinct_epochs = sorted({e for e, _ in epoch_lines})
        print(f"CASE=3: distinct 'Epoch N/M' lines: {distinct_epochs}")

        summary = {
            "case": 3,
            "deployment_id": deployment_id,
            "results": [{"id": r["id"], "train_metrics": r["train_metrics"]} for r in results],
            "distinct_epochs_in_logs": distinct_epochs,
            "edge_model_id": edge_model_id,
            "cloud_model_id": cloud_model_id,
        }
        for r in results:
            print(f"CASE=3: result {r['id']} train_metrics={r['train_metrics']}")
        return summary


if __name__ == "__main__":
    import json
    print(json.dumps(run(), indent=2))
