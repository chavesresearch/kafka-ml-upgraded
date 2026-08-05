"""CASE=9 (BlockchainSingleFederatedTraining, TensorFlow) - real MNIST,
5 real local epochs per round, across 5 real aggregation rounds, real
on-chain round coordination against the local Anvil devnet.

Same shape as CASE=5, but `blockchain=True` - backend dispatches to
CASE=9 instead of 5 (`app/controllers/deployments.py`: `5 if not
deployment.blockchain else 9`). Real `FederatedLearning` smart contract
deployment + on-chain round coordination + ERC20 reward transfer, not
mocked - see kustomize/local/resources/blockchain-devnet.yaml.
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
    x, y = load_mnist_train_subset(N_TRAIN, seed=9)
    print(f"CASE=9: loaded {len(x)} real MNIST train images")

    before_pods = kubectl_pod_names()

    with api_client() as client:
        model_id = create_model(client, f"mnist-case9-model-{run_id}", MNIST_SINGLE_MODEL_CODE, framework="tf")
        config_id = create_configuration(client, f"mnist-case9-config-{run_id}", [model_id])
        deployment_id = create_deployment(
            client,
            configuration=config_id,
            batch=32,
            tf_kwargs_fit=f"epochs={EPOCHS}",
            tf_kwargs_val="",
            incremental=False,
            federated=True,
            blockchain=True,
            agg_rounds=AGG_ROUNDS,
            min_data=100,
            agg_strategy="FedAvg",
            data_restriction={},
            conf_mat_settings=False,
        )
        print(f"CASE=9: deployment {deployment_id} created, streaming {N_TRAIN} real MNIST images...")

        topic = f"mnist-case9-data-{run_id}"
        sink = FederatedRawSink(
            boostrap_servers=BOOTSTRAP_SERVERS,
            topic=topic,
            deployment_id=deployment_id,
            description="mnist-case9",
            validation_rate=0.15,
            test_rate=0.1,
        )
        for xi, yi in zip(x, y):
            sink.send(data=xi, label=yi)
        sink.close()
        print("CASE=9: all MNIST data sent, waiting for 5 on-chain federated rounds to finish...")

        results = wait_for_status(client, deployment_id, "finished", timeout_s=900)
        assert len(results) == 1
        result = results[0]
        train_metrics = result["train_metrics"]
        print(f"CASE=9: result {result['id']} train_metrics={train_metrics}")
        n_round_values = len(train_metrics.get("accuracy", []))
        print(f"CASE=9: train_metrics accuracy history has {n_round_values} entries (expected {AGG_ROUNDS} rounds)")

        pods = new_pods(before_pods)
        print(f"CASE=9: new pods since deployment: {pods}")
        epoch_lines = []
        for p in pods:
            epoch_lines += epoch_progress_lines(kubectl_logs(p))
        distinct_epochs = sorted({e for e, _ in epoch_lines})
        print(f"CASE=9: distinct 'Epoch N/M' lines: {distinct_epochs} (total occurrences: {len(epoch_lines)})")

        return {
            "case": 9,
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
