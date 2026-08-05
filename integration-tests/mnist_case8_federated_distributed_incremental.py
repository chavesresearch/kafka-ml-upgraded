"""CASE=8 (DistributedFederatedIncrementalTraining, TensorFlow) - real
MNIST, 5 real local epochs per round, across 5 real aggregation rounds,
distributed father/child pair, fed via a continuous streaming trickle.

Combines CASE=6 (discrete round-sized bursts with a genuine silence gap
between them, longer than stream_timeout - see that file's docstring for
why *both* a fixed one-shot trickle *and* a continuous no-gap trickle
fail here, for two different reasons) and CASE=7 (distributed father/child
pair, edge submodel's own input shape).
"""

import threading
import uuid

from kafkaml_datasources import OnlineFederatedRawSink

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

STREAM_TIMEOUT_S = 30
N_PER_BURST = 20
BURST_SEND_GAP_S = 1.5
SILENCE_GAP_S = STREAM_TIMEOUT_S + 15
N_BURSTS = 8
MAX_TRICKLE_S = (N_PER_BURST // 4 * BURST_SEND_GAP_S + SILENCE_GAP_S) * N_BURSTS + 120
EPOCHS = 5
AGG_ROUNDS = 5


def run():
    run_id = uuid.uuid4().hex[:8]
    x, y = load_mnist_train_subset(2000, seed=8)
    print(f"CASE=8: loaded {len(x)} real MNIST train images to trickle from")

    before_pods = kubectl_pod_names()
    stop_event = threading.Event()

    with api_client() as client:
        cloud_model_id = create_model(
            client, f"mnist-case8-cloud-{run_id}", MNIST_CLOUD_MODEL_CODE, framework="tf", distributed=True
        )
        edge_model_id = create_model(
            client,
            f"mnist-case8-edge-{run_id}",
            MNIST_EDGE_MODEL_CODE,
            framework="tf",
            distributed=True,
            father=cloud_model_id,
        )
        config_id = create_configuration(client, f"mnist-case8-config-{run_id}", [cloud_model_id])
        deployment_id = create_deployment(
            client,
            configuration=config_id,
            batch=8,
            tf_kwargs_fit=f"epochs={EPOCHS}",
            tf_kwargs_val="",
            incremental=True,
            indefinite=False,
            stream_timeout=30000,
            monitoring_metric="loss",
            change="down",
            improvement=0.05,
            federated=True,
            agg_rounds=AGG_ROUNDS,
            min_data=5,
            agg_strategy="FedAvg",
            data_restriction={},
            optimizer="adam",
            learning_rate=0.001,
            loss="sparse_categorical_crossentropy",
            metrics="accuracy",
            conf_mat_settings=False,
        )
        print(f"CASE=8: deployment {deployment_id} created (cloud={cloud_model_id}, edge={edge_model_id})")

        topic = f"mnist-case8-data-{run_id}"
        sink = OnlineFederatedRawSink(
            boostrap_servers=BOOTSTRAP_SERVERS,
            topic=topic,
            deployment_id=deployment_id,
            description="mnist-case8",
            validation_rate=0.15,
        )
        sink.send_online_control_msg(x[0], y[0])

        sent_count = {"n": 1}

        def trickle():
            idx = 1
            for burst in range(N_BURSTS):
                if stop_event.is_set():
                    return
                for i in range(0, N_PER_BURST, 4):
                    if stop_event.is_set():
                        return
                    for _ in range(4):
                        xi, yi = x[idx % len(x)], y[idx % len(x)]
                        sink.send(data=xi, label=yi)
                        idx += 1
                    sent_count["n"] = idx
                    stop_event.wait(BURST_SEND_GAP_S)
                print(f"CASE=8: burst {burst + 1}/{N_BURSTS} sent ({N_PER_BURST} images), "
                      f"now pausing {SILENCE_GAP_S}s so this round's stream can exhaust...")
                stop_event.wait(SILENCE_GAP_S)

        sender_thread = threading.Thread(target=trickle, daemon=True)
        sender_thread.start()
        print(f"CASE=8: background burst sender started ({N_BURSTS} bursts of {N_PER_BURST}, "
              f"{SILENCE_GAP_S}s silence gap each), waiting for 5 federated rounds to finish...")

        try:
            results = wait_for_status(client, deployment_id, "finished", timeout_s=MAX_TRICKLE_S + 60, min_results=2)
        finally:
            stop_event.set()
            sender_thread.join(timeout=10)
            print(f"CASE=8: sender sent {sent_count['n']} real MNIST images total before stopping")

        assert len(results) == 2, f"expected 2 results, got {len(results)}"

        pods = new_pods(before_pods)
        print(f"CASE=8: new pods since deployment: {pods}")
        epoch_lines = []
        for p in pods:
            epoch_lines += epoch_progress_lines(kubectl_logs(p))
        distinct_epochs = sorted({e for e, _ in epoch_lines})
        print(f"CASE=8: distinct 'Epoch N/M' lines: {distinct_epochs} (total occurrences: {len(epoch_lines)})")

        for r in results:
            print(f"CASE=8: result {r['id']} train_metrics={r['train_metrics']}")

        return {
            "case": 8,
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
