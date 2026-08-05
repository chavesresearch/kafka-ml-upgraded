"""Shared real-inference verification helper for the MNIST pass.

Deploys a trained result for real-time inference through the real
`kafkaml_client` SDK (`POST /results/inference/{id}`, which makes
`backend` create a real Kubernetes `ReplicationController` - not
simulated, not a direct model.predict() call) - then explicitly confirms
via `kubectl` that a real pod matching that ReplicationController's
selector (`app=inference{inference_id}`, see
backend/app/controllers/inferences.py's `_single_inference_manifest`/
`_distributed_inference_manifest`) actually landed and became Ready in
the `kafkaml` namespace, before sending any data - this is the concrete
evidence the deployment is real, not an assumption that the API call
succeeding implies a healthy running workload.

Sends one real held-out MNIST test image (never used in any training
run) and reads the prediction back over the real output Kafka topic.
Input/output here use plain `kafka.KafkaProducer`/`KafkaConsumer`
directly, matching examples/MNIST_RAW_format/mnist_dataset_inference_example.py -
the framework's own official example for RAW-format inference testing.
There is no dedicated kafka-ml SDK class for this: `kafkaml_datasources`
only has `AvroInference` (AVRO format only) - RAW-format inference input/
output is just plain Kafka topics by design, so any producer/consumer
(this script, a real IoT device, `kafka-console-producer`, ...) can drive
it exactly this way.
"""

import json
import subprocess
import time

from kafka import KafkaConsumer, KafkaProducer

from common import BOOTSTRAP_SERVERS
from mnist_common import NAMESPACE, load_mnist_test_sample


def _wait_for_inference_pod(inference_id: int, case_label: str, timeout_s: int = 60) -> dict:
    """Polls `kubectl` until a real pod matching this inference's
    ReplicationController selector is Running - proof the deployment
    landed as a real Kubernetes workload, not just a 2xx from the API."""
    selector = f"app=inference{inference_id}"
    deadline = time.time() + timeout_s
    last_seen = "no pod found yet"
    while time.time() < deadline:
        out = subprocess.run(
            ["kubectl", "get", "pods", "-n", NAMESPACE, "-l", selector,
             "-o", "jsonpath={.items[0].metadata.name} {.items[0].status.phase} {.items[0].spec.nodeName}"],
            capture_output=True, text=True,
        )
        if out.returncode == 0 and out.stdout.strip():
            name, phase, node = (out.stdout.strip().split(" ") + ["", ""])[:3]
            last_seen = f"{name} phase={phase} node={node}"
            if phase == "Running":
                print(f"[{case_label}] kubectl confirms real inference pod: {last_seen}")
                return {"pod_name": name, "phase": phase, "node": node}
        time.sleep(2)
    raise AssertionError(
        f"[{case_label}] no Running pod found for selector {selector} in {timeout_s}s (last seen: {last_seen})"
    )


def deploy_and_test_inference(
    client,
    result_id: int,
    run_id: str,
    case_label: str,
    distributed: bool = False,
    test_index: int = 0,
    wait_s: int = 25,
) -> dict:
    x_test, true_label = load_mnist_test_sample(test_index)

    input_topic = f"mnist-inf-in-{case_label}-{run_id}"
    output_topic = f"mnist-inf-out-{case_label}-{run_id}"

    fields: dict = {}
    if distributed:
        # See backend/app/controllers/inferences.py's _distributed_inference_manifest:
        # `distributed` mode (2-output model.predict() unpacking) is only
        # triggered in model_inference/tensorflow's inference.py when LIMIT
        # evals to a real float, not the string "None" - an explicit
        # limit=0.0 makes max(prediction_value) < limit always False, so
        # this stays a clean single-hop test (never forwards to output_upper).
        fields["limit"] = 0.0
        fields["output_upper"] = f"mnist-inf-upper-{case_label}-{run_id}"

    inference_id = client.deploy_inference(
        result_id,
        input_topic=input_topic,
        output_topic=output_topic,
        input_format="RAW",
        input_config=json.dumps({"data_type": "uint8", "data_reshape": "28 28"}),
        replicas=1,
        gpumem=0,
        **fields,
    )

    try:
        pod_info = _wait_for_inference_pod(inference_id, case_label)
        # Give the now-confirmed-Running pod a little more time to finish
        # downloading the trained model and join its Kafka consumer group
        # (Running != ready-to-consume - model download/TF import happens
        # after the container starts).
        time.sleep(wait_s)

        producer = KafkaProducer(bootstrap_servers=BOOTSTRAP_SERVERS)
        producer.send(input_topic, x_test.tobytes())
        producer.flush()
        producer.close()

        consumer = KafkaConsumer(
            output_topic,
            bootstrap_servers=BOOTSTRAP_SERVERS,
            auto_offset_reset="earliest",
            consumer_timeout_ms=45000,
        )
        prediction = None
        for msg in consumer:
            prediction = json.loads(msg.value.decode("utf-8"))
            break
        consumer.close()

        assert prediction is not None, f"[{case_label}] no prediction received on {output_topic}"
        assert "values" in prediction and len(prediction["values"]) == 10, (
            f"[{case_label}] expected a 10-value softmax prediction, got {prediction}"
        )
        predicted_digit = max(range(10), key=lambda i: prediction["values"][i])
        print(
            f"[{case_label}] inference OK - inference_id={inference_id} true_label={true_label} "
            f"predicted={predicted_digit} values={prediction['values']}"
        )
        return {
            "inference_id": inference_id,
            "k8s_pod": pod_info,
            "true_label": true_label,
            "predicted_digit": predicted_digit,
            "values": prediction["values"],
        }
    finally:
        client.stop_inference(inference_id)
        client.delete_inference(inference_id)
