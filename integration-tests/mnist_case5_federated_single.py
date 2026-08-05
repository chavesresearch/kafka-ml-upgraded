"""CASE=5 (SingleFederatedTraining, TensorFlow) - real MNIST, 5 real local
epochs per aggregation round, across 5 real aggregation rounds.

Real multi-service federated round (main trainer, both control-loggers,
federated_backend, a real edge worker Job - see
model_training/tensorflow/CLAUDE.md's CASE=5 section) with real MNIST
data and `agg_rounds=5`. The edge worker's `classicFederatedTraining`
loop (federated-module/federated_model_training/tensorflow/classic_federated_training.py)
is a single long-lived Job that participates in all 5 rounds - each
round it re-fits `epochs=5` on the same locally-cached data and sends
weights back, so this really does exercise 5 rounds x 5 real epochs.
"""

import uuid

from kafkaml_datasources import FederatedRawSink

from common import BOOTSTRAP_SERVERS, api_client, create_configuration, create_deployment, create_model, wait_for_status
from mnist_common import (
    MNIST_SINGLE_MODEL_CODE,
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
    x, y = load_mnist_train_subset(N_TRAIN, seed=5)
    print(f"CASE=5: loaded {len(x)} real MNIST train images")

    before_pods = kubectl_pod_names()

    with api_client() as client:
        model_id = create_model(client, f"mnist-case5-model-{run_id}", MNIST_SINGLE_MODEL_CODE, framework="tf")
        config_id = create_configuration(client, f"mnist-case5-config-{run_id}", [model_id])
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
            conf_mat_settings=False,
        )
        print(f"CASE=5: deployment {deployment_id} created, streaming {N_TRAIN} real MNIST images...")

        topic = f"mnist-case5-data-{run_id}"
        sink = FederatedRawSink(
            boostrap_servers=BOOTSTRAP_SERVERS,
            topic=topic,
            deployment_id=deployment_id,
            description="mnist-case5",
            validation_rate=0.15,
            test_rate=0.1,
        )
        for xi, yi in zip(x, y):
            sink.send(data=xi, label=yi)
        sink.close()
        print("CASE=5: all MNIST data sent, waiting for 5 federated rounds to finish...")

        results = wait_for_status(client, deployment_id, "finished", timeout_s=900)
        assert len(results) == 1
        result = results[0]
        train_metrics = result["train_metrics"]
        print(f"CASE=5: result {result['id']} train_metrics={train_metrics}")
        n_round_values = len(train_metrics.get("accuracy", []))
        print(f"CASE=5: train_metrics accuracy history has {n_round_values} entries (expected {AGG_ROUNDS} rounds)")

        pods = new_pods(before_pods)
        print(f"CASE=5: new pods since deployment: {pods}")
        epoch_lines = []
        for p in pods:
            epoch_lines += epoch_progress_lines(kubectl_logs(p))
        distinct_epochs = sorted({e for e, _ in epoch_lines})
        print(f"CASE=5: distinct 'Epoch N/M' lines across all pods/rounds: {distinct_epochs} (total occurrences: {len(epoch_lines)})")

        return {
            "case": 5,
            "deployment_id": deployment_id,
            "result_id": result["id"],
            "n_round_metric_values": n_round_values,
            "distinct_epochs_in_logs": distinct_epochs,
            "total_epoch_lines": len(epoch_lines),
            "train_metrics": train_metrics,
        }


if __name__ == "__main__":
    import json
    print(json.dumps(run(), indent=2))
