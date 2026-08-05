"""CASE=2 (SingleIncrementalTraining, TensorFlow) - real MNIST, 5 real
epochs per streaming burst.

Same real streaming approach as test_case2 (`OnlineRawSink`, two bursts),
but real MNIST images in 3 bursts and `tf_kwargs_fit="epochs=5"` - each
burst triggers its own real multi-epoch `.fit()` call on that burst's
data (incremental training has no single global "epoch count", each
streaming mini-batch gets its own full epochs=5 pass - see
docs/usage/incremental-training.md). Verified via real "Epoch N/5" lines
in the pod logs, once per burst.
"""

import time
import uuid

from kafkaml_datasources import OnlineRawSink

from common import BOOTSTRAP_SERVERS, api_client, create_configuration, create_deployment, create_model, wait_for_status
from mnist_common import (
    MNIST_SINGLE_MODEL_CODE,
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
    x, y = load_mnist_train_subset(N_PER_BURST * N_BURSTS, seed=2)
    print(f"CASE=2: loaded {len(x)} real MNIST train images for {N_BURSTS} bursts")

    before_pods = kubectl_pod_names()

    with api_client() as client:
        model_id = create_model(client, f"mnist-case2-model-{run_id}", MNIST_SINGLE_MODEL_CODE, framework="tf")
        config_id = create_configuration(client, f"mnist-case2-config-{run_id}", [model_id])
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
            conf_mat_settings=False,
        )
        print(f"CASE=2: deployment {deployment_id} created, waiting for trainer to join consumer group...")

        time.sleep(20)

        topic = f"mnist-case2-data-{run_id}"
        sink = OnlineRawSink(
            boostrap_servers=BOOTSTRAP_SERVERS,
            topic=topic,
            deployment_id=deployment_id,
            description="mnist-case2",
            validation_rate=0.15,
        )
        for b in range(N_BURSTS):
            burst_x = x[b * N_PER_BURST : (b + 1) * N_PER_BURST]
            burst_y = y[b * N_PER_BURST : (b + 1) * N_PER_BURST]
            for xi, yi in zip(burst_x, burst_y):
                sink.send(data=xi, label=yi)
            print(f"CASE=2: burst {b + 1}/{N_BURSTS} sent ({N_PER_BURST} images)")
            time.sleep(12)

        print("CASE=2: all bursts sent, waiting for stream_timeout + training to finish...")
        results = wait_for_status(client, deployment_id, "finished", timeout_s=600)
        assert len(results) == 1
        result = results[0]
        train_metrics = result["train_metrics"]
        print(f"CASE=2: result {result['id']} train_metrics={train_metrics}")

        pods = new_pods(before_pods)
        print(f"CASE=2: new pods since deployment: {pods}")
        epoch_lines = []
        for p in pods:
            epoch_lines += epoch_progress_lines(kubectl_logs(p))
        distinct_epochs = sorted({e for e, _ in epoch_lines})
        print(f"CASE=2: distinct 'Epoch N/M' lines across all bursts: {distinct_epochs} (total occurrences: {len(epoch_lines)})")

        return {
            "case": 2,
            "deployment_id": deployment_id,
            "result_id": result["id"],
            "distinct_epochs_in_logs": distinct_epochs,
            "total_epoch_lines": len(epoch_lines),
            "train_metrics": train_metrics,
        }


if __name__ == "__main__":
    import json
    print(json.dumps(run(), indent=2))
