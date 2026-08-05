"""CASE=6 (SingleFederatedIncrementalTraining, TensorFlow) - real MNIST,
5 real local epochs per round, across 5 real aggregation rounds, fed via
a continuous streaming trickle (`OnlineFederatedRawSink`).

Getting the data-sending timing right here took two failed attempts,
both instructive about how CASE=6 actually behaves - worth keeping this
history rather than just the final working version:

1. A fixed ~90s one-shot trickle (matching test_case6_federated_incremental.py's
   tiny-synthetic-data timing) hit a real, previously-undiscovered
   deadlock: round 1 consumed all the data and finished, but round 2
   onward had nothing left to train on and hung forever -
   `train_incremental_model`'s retry-on-empty loop was re-iterating an
   already-exhausted Python generator, which is a permanent no-op, not a
   fresh poll (fixed in federated_mainTraining.py - see that fix's
   comment for the full diagnosis).
2. With that fix in place, a *continuous* trickle (send-then-sleep(3s),
   forever) was tried next - but that made round 0 never end: the inner
   `for mini_ds in self.kafka_dataset:` loop in `train_incremental_model`
   only returns once `stream_timeout` (30s) passes with *zero* new
   messages, so a steady stream with no real gap just keeps feeding round
   0 forever, endlessly re-fitting, never reaching round 1 (confirmed in
   the worker's own logs: dozens of back-to-back "Received 4 new
   message(s)" -> 5-epoch fit() cycles, all still logged under the same
   "Round: 0").

The fix: send **discrete, round-sized bursts with a genuine silence gap
between them** (longer than `stream_timeout`), so each round's stream can
actually observe "no new data" and hand control back to
`classicFederatedTraining.py`'s outer loop for the next round's model
broadcast - which is what lets a *new* streaming consumer join for the
next round in the first place.
"""

import threading
import uuid

from kafkaml_datasources import OnlineFederatedRawSink

from common import BOOTSTRAP_SERVERS, api_client, create_configuration, create_deployment, create_model, wait_for_status
from mnist_common import (
    MNIST_SINGLE_MODEL_CODE,
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
    # Real MNIST images, cycled if the run outlasts this pool - still real
    # digit images each time, just reused across a long run rather than
    # downloading/holding an enormous one-shot array.
    x, y = load_mnist_train_subset(2000, seed=6)
    print(f"CASE=6: loaded {len(x)} real MNIST train images to trickle from")

    before_pods = kubectl_pod_names()
    stop_event = threading.Event()

    with api_client() as client:
        model_id = create_model(client, f"mnist-case6-model-{run_id}", MNIST_SINGLE_MODEL_CODE, framework="tf")
        config_id = create_configuration(client, f"mnist-case6-config-{run_id}", [model_id])
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
            conf_mat_settings=False,
        )
        print(f"CASE=6: deployment {deployment_id} created")

        topic = f"mnist-case6-data-{run_id}"
        sink = OnlineFederatedRawSink(
            boostrap_servers=BOOTSTRAP_SERVERS,
            topic=topic,
            deployment_id=deployment_id,
            description="mnist-case6",
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
                print(f"CASE=6: burst {burst + 1}/{N_BURSTS} sent ({N_PER_BURST} images), "
                      f"now pausing {SILENCE_GAP_S}s so this round's stream can exhaust...")
                stop_event.wait(SILENCE_GAP_S)

        sender_thread = threading.Thread(target=trickle, daemon=True)
        sender_thread.start()
        print(f"CASE=6: background burst sender started ({N_BURSTS} bursts of {N_PER_BURST}, "
              f"{SILENCE_GAP_S}s silence gap each), waiting for 5 federated rounds to finish...")

        try:
            results = wait_for_status(client, deployment_id, "finished", timeout_s=MAX_TRICKLE_S + 60)
        finally:
            stop_event.set()
            sender_thread.join(timeout=10)
            print(f"CASE=6: sender sent {sent_count['n']} real MNIST images total before stopping")

        assert len(results) == 1
        result = results[0]
        train_metrics = result["train_metrics"]
        print(f"CASE=6: result {result['id']} train_metrics={train_metrics}")
        n_round_values = len(train_metrics.get("accuracy", []))
        print(f"CASE=6: train_metrics accuracy history has {n_round_values} entries")

        pods = new_pods(before_pods)
        print(f"CASE=6: new pods since deployment: {pods}")
        epoch_lines = []
        for p in pods:
            epoch_lines += epoch_progress_lines(kubectl_logs(p))
        distinct_epochs = sorted({e for e, _ in epoch_lines})
        print(f"CASE=6: distinct 'Epoch N/M' lines: {distinct_epochs} (total occurrences: {len(epoch_lines)})")

        return {
            "case": 6,
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
