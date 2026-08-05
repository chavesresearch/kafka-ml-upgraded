"""CASE=1 (SingleClassicTraining, TensorFlow) - real MNIST, 5 real epochs.

Same real API + real Kafka approach as test_case1_single_classic.py, but
with real MNIST digit images (not synthetic scalar data) and
`tf_kwargs_fit="epochs=5"`, to verify genuine multi-epoch training - not
just that a single fit() call succeeds. Verification checks both the
result's per-epoch metric history length (`parse_metrics` appends one
value per epoch, see mainTraining.py) AND the training pod's real logs
for 5 distinct "Epoch N/5" lines.
"""

import uuid

from kafkaml_datasources import RawSink

from common import BOOTSTRAP_SERVERS, api_client, create_configuration, create_deployment, create_model, wait_for_status
from mnist_common import (
    MNIST_SINGLE_MODEL_CODE,
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
    x, y = load_mnist_train_subset(N_TRAIN, seed=1)
    print(f"CASE=1: loaded {len(x)} real MNIST train images")

    before_pods = kubectl_pod_names()

    with api_client() as client:
        model_id = create_model(client, f"mnist-case1-model-{run_id}", MNIST_SINGLE_MODEL_CODE, framework="tf")
        config_id = create_configuration(client, f"mnist-case1-config-{run_id}", [model_id])
        deployment_id = create_deployment(
            client,
            configuration=config_id,
            batch=32,
            tf_kwargs_fit=f"epochs={EPOCHS}",
            tf_kwargs_val="",
            incremental=False,
            federated=False,
            conf_mat_settings=False,
        )
        print(f"CASE=1: deployment {deployment_id} created, streaming {N_TRAIN} real MNIST images...")

        topic = f"mnist-case1-data-{run_id}"
        sink = RawSink(
            boostrap_servers=BOOTSTRAP_SERVERS,
            topic=topic,
            deployment_id=deployment_id,
            description="mnist-case1",
            validation_rate=0.15,
            test_rate=0.1,
        )
        for xi, yi in zip(x, y):
            sink.send(data=xi, label=yi)
        sink.close()
        print("CASE=1: all MNIST data sent, waiting for training to finish...")

        results = wait_for_status(client, deployment_id, "finished", timeout_s=600)
        assert len(results) == 1
        result = results[0]
        train_metrics = result["train_metrics"]
        print(f"CASE=1: result {result['id']} train_metrics={train_metrics}")

        assert "accuracy" in train_metrics and "loss" in train_metrics
        n_epoch_values = len(train_metrics["accuracy"])
        print(f"CASE=1: train_metrics accuracy history has {n_epoch_values} entries (expected {EPOCHS})")

        pods = new_pods(before_pods)
        print(f"CASE=1: new pods since deployment: {pods}")
        epoch_lines = []
        for p in pods:
            if "training" in p or "case1" in p:
                epoch_lines += epoch_progress_lines(kubectl_logs(p))
        distinct_epochs = sorted({e for e, _ in epoch_lines})
        print(f"CASE=1: distinct 'Epoch N/M' lines seen in pod logs: {distinct_epochs}")

        return {
            "case": 1,
            "deployment_id": deployment_id,
            "result_id": result["id"],
            "n_epoch_metric_values": n_epoch_values,
            "distinct_epochs_in_logs": distinct_epochs,
            "train_metrics": train_metrics,
        }


if __name__ == "__main__":
    import json
    print(json.dumps(run(), indent=2))
