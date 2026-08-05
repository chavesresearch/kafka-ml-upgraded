"""CASE=4 (DistributedIncrementalTraining, TensorFlow) - real MNIST, 5 real
epochs per streaming burst, distributed father/child pair.

Combines CASE=2 (OnlineRawSink bursts) and CASE=3 (distributed pair).
Longer pre-send wait than CASE=2 - two model downloads + building the
combined multi-output graph takes measurably longer before the streaming
consumer group actually joins (see test_case4_distributed_incremental.py's
own comment / model_training/tensorflow/CLAUDE.md).
"""

import time
import uuid

from kafkaml_datasources import OnlineRawSink

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

N_PER_BURST = 40
N_BURSTS = 3
EPOCHS = 5


def run():
    run_id = uuid.uuid4().hex[:8]
    x, y = load_mnist_train_subset(N_PER_BURST * N_BURSTS, seed=4)
    print(f"CASE=4: loaded {len(x)} real MNIST train images for {N_BURSTS} bursts")

    before_pods = kubectl_pod_names()

    with api_client() as client:
        cloud_model_id = create_model(
            client, f"mnist-case4-cloud-{run_id}", MNIST_CLOUD_MODEL_CODE, framework="tf", distributed=True
        )
        edge_model_id = create_model(
            client,
            f"mnist-case4-edge-{run_id}",
            MNIST_EDGE_MODEL_CODE,
            framework="tf",
            distributed=True,
            father=cloud_model_id,
        )
        config_id = create_configuration(client, f"mnist-case4-config-{run_id}", [cloud_model_id])
        deployment_id = create_deployment(
            client,
            configuration=config_id,
            batch=8,
            tf_kwargs_fit=f"epochs={EPOCHS}",
            tf_kwargs_val="",
            incremental=True,
            indefinite=False,
            stream_timeout=45000,
            monitoring_metric="loss",
            change="down",
            improvement=0.05,
            federated=False,
            optimizer="adam",
            learning_rate=0.001,
            loss="sparse_categorical_crossentropy",
            metrics="accuracy",
            conf_mat_settings=False,
        )
        print(f"CASE=4: deployment {deployment_id} created (cloud={cloud_model_id}, edge={edge_model_id})")

        time.sleep(35)

        topic = f"mnist-case4-data-{run_id}"
        sink = OnlineRawSink(
            boostrap_servers=BOOTSTRAP_SERVERS,
            topic=topic,
            deployment_id=deployment_id,
            description="mnist-case4",
            validation_rate=0.15,
        )
        for b in range(N_BURSTS):
            burst_x = x[b * N_PER_BURST : (b + 1) * N_PER_BURST]
            burst_y = y[b * N_PER_BURST : (b + 1) * N_PER_BURST]
            for xi, yi in zip(burst_x, burst_y):
                sink.send(data=xi, label=yi)
            print(f"CASE=4: burst {b + 1}/{N_BURSTS} sent ({N_PER_BURST} images)")
            time.sleep(12)

        print("CASE=4: all bursts sent, waiting for stream_timeout + training to finish...")
        results = wait_for_status(client, deployment_id, "finished", timeout_s=600, min_results=2)
        assert len(results) == 2, f"expected 2 results, got {len(results)}"

        pods = new_pods(before_pods)
        print(f"CASE=4: new pods since deployment: {pods}")
        epoch_lines = []
        for p in pods:
            epoch_lines += epoch_progress_lines(kubectl_logs(p))
        distinct_epochs = sorted({e for e, _ in epoch_lines})
        print(f"CASE=4: distinct 'Epoch N/M' lines: {distinct_epochs} (total occurrences: {len(epoch_lines)})")

        for r in results:
            print(f"CASE=4: result {r['id']} train_metrics={r['train_metrics']}")

        return {
            "case": 4,
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
