"""Deploys real-time inference for an existing TrainingResult and verifies
one real prediction - same as mnist_inference_common.deploy_and_test_inference,
but deliberately does NOT stop/delete the Inference afterward, so it stays
visible (and running) in the frontend UI. Ad hoc, not part of the committed
suite - leaves a real ReplicationController running per call, clean up
manually via the UI or `client.stop_inference`/`delete_inference` when done.

Usage: uv run python3 deploy_inference_persist.py <result_id> <case_label> [mnist|scalar] [--distributed]
"""

import json
import sys
import time
import uuid

from kafka import KafkaConsumer, KafkaProducer

from common import BOOTSTRAP_SERVERS, api_client
from mnist_common import load_mnist_test_sample
from mnist_inference_common import _wait_for_inference_pod


def deploy_mnist(client, result_id: int, case_label: str, distributed: bool) -> dict:
    run_id = uuid.uuid4().hex[:8]
    x_test, true_label = load_mnist_test_sample(0)

    input_topic = f"persist-inf-in-{case_label}-{run_id}"
    output_topic = f"persist-inf-out-{case_label}-{run_id}"

    fields: dict = {}
    if distributed:
        fields["limit"] = 0.0
        fields["output_upper"] = f"persist-inf-upper-{case_label}-{run_id}"

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

    pod_info = _wait_for_inference_pod(inference_id, case_label)
    time.sleep(25)

    producer = KafkaProducer(bootstrap_servers=BOOTSTRAP_SERVERS)
    producer.send(input_topic, x_test.tobytes())
    producer.flush()
    producer.close()

    consumer = KafkaConsumer(
        output_topic, bootstrap_servers=BOOTSTRAP_SERVERS,
        auto_offset_reset="earliest", consumer_timeout_ms=45000,
    )
    prediction = None
    for msg in consumer:
        prediction = json.loads(msg.value.decode("utf-8"))
        break
    consumer.close()

    assert prediction is not None, f"[{case_label}] no prediction received"
    predicted_digit = max(range(10), key=lambda i: prediction["values"][i])
    print(f"[{case_label}] inference_id={inference_id} true_label={true_label} predicted={predicted_digit} - LEFT RUNNING")
    return {"inference_id": inference_id, "pod": pod_info, "true_label": true_label, "predicted": predicted_digit}


def deploy_scalar(client, result_id: int, case_label: str) -> dict:
    import struct
    run_id = uuid.uuid4().hex[:8]
    input_topic = f"persist-inf-in-{case_label}-{run_id}"
    output_topic = f"persist-inf-out-{case_label}-{run_id}"

    inference_id = client.deploy_inference(
        result_id,
        input_topic=input_topic,
        output_topic=output_topic,
        input_format="RAW",
        input_config=json.dumps({"data_type": "float32", "data_reshape": "1"}),
        replicas=1,
        gpumem=0,
    )

    pod_info = _wait_for_inference_pod(inference_id, case_label)
    time.sleep(25)

    test_x = 0.9
    producer = KafkaProducer(bootstrap_servers=BOOTSTRAP_SERVERS)
    producer.send(input_topic, struct.pack("f", test_x))
    producer.flush()
    producer.close()

    consumer = KafkaConsumer(
        output_topic, bootstrap_servers=BOOTSTRAP_SERVERS,
        auto_offset_reset="earliest", consumer_timeout_ms=45000,
    )
    prediction = None
    for msg in consumer:
        prediction = json.loads(msg.value.decode("utf-8"))
        break
    consumer.close()

    assert prediction is not None, f"[{case_label}] no prediction received"
    print(f"[{case_label}] inference_id={inference_id} x={test_x} raw={prediction['values']} - LEFT RUNNING")
    return {"inference_id": inference_id, "pod": pod_info, "raw_values": prediction["values"]}


def main():
    result_id = int(sys.argv[1])
    case_label = sys.argv[2]
    kind = sys.argv[3] if len(sys.argv) > 3 else "mnist"
    distributed = "--distributed" in sys.argv

    with api_client() as client:
        if kind == "scalar":
            summary = deploy_scalar(client, result_id, case_label)
        else:
            summary = deploy_mnist(client, result_id, case_label, distributed)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
