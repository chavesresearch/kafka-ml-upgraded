"""Ad hoc driver: PyTorch classic training (real API + real Kafka, same
shape as test_pytorch_classic.py) followed by real inference deployment
and a real prediction check - closing the same training-only gap
run_case_with_inference.py closes for the TF mnist_case*.py scripts.
PyTorch has no CASE dispatch and no committed inference test in this
suite (see integration-tests/README.md's "what isn't covered" list) -
not part of the committed suite, a throwaway verification script for
this session's post-wipe regression pass.
"""

import json
import struct
import time
import uuid

import numpy as np
from kafka import KafkaConsumer, KafkaProducer
from kafkaml_datasources import RawSink

from common import (
    BOOTSTRAP_SERVERS,
    PTH_MODEL_CODE,
    api_client,
    create_configuration,
    create_deployment,
    create_model,
    wait_for_status,
)


def main() -> None:
    run_id = uuid.uuid4().hex[:8]

    with api_client() as client:
        model_id = create_model(client, f"it-pth-model-{run_id}", PTH_MODEL_CODE, framework="pth")
        config_id = create_configuration(client, f"it-pth-config-{run_id}", [model_id])
        deployment_id = create_deployment(
            client,
            configuration=config_id,
            batch=4,
            pth_kwargs_fit="max_epochs=1",
            pth_kwargs_val="",
            incremental=False,
            federated=False,
            conf_mat_settings=False,
        )
        print(f"PyTorch: deployment {deployment_id} created")

        topic = f"it-pth-data-{run_id}"
        sink = RawSink(
            boostrap_servers=BOOTSTRAP_SERVERS,
            topic=topic,
            deployment_id=deployment_id,
            description="pytorch-with-inference",
            validation_rate=0.2,
            test_rate=0.1,
        )
        rng = np.random.default_rng(5)
        for _ in range(40):
            x = rng.random(1).astype(np.float32)
            y = np.array([int(x[0] > 0.5)], dtype=np.uint8)
            sink.send(x, y)
        sink.close()
        print("PyTorch: all data sent, waiting for training to finish...")

        results = wait_for_status(client, deployment_id, "finished")
        assert len(results) == 1
        result = results[0]
        print(f"PyTorch: result {result['id']} train_metrics={result['train_metrics']}")

        input_topic = f"it-pth-inf-in-{run_id}"
        output_topic = f"it-pth-inf-out-{run_id}"
        inference_id = client.deploy_inference(
            result["id"],
            input_topic=input_topic,
            output_topic=output_topic,
            input_format="RAW",
            input_config=json.dumps({"data_type": "float32", "data_reshape": "1"}),
            replicas=1,
            gpumem=0,
        )
        print(f"PyTorch: inference {inference_id} deployed")

        try:
            time.sleep(25)

            test_x = 0.9  # clearly > 0.5, expected class 1
            producer = KafkaProducer(bootstrap_servers=BOOTSTRAP_SERVERS)
            producer.send(input_topic, struct.pack("f", test_x))
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

            assert prediction is not None, "no prediction received on the output topic"
            assert "values" in prediction, f"unexpected prediction shape: {prediction}"
            # Real shape confirmed in model_inference/CLAUDE.md:
            # {"values": [[[logit0, logit1]]]} - a raw (batch, 1, 2) logit
            # pair, no softmax (matches PTH_MODEL_CODE's forward()).
            flat = prediction["values"]
            while isinstance(flat, list) and isinstance(flat[0], list):
                flat = flat[0]
            predicted_class = int(flat[1] > flat[0])
            print(
                f"PyTorch: inference OK - x={test_x} predicted_class={predicted_class} "
                f"(expected 1) raw={prediction['values']}"
            )
            summary = {
                "training": {"result_id": result["id"], "train_metrics": result["train_metrics"]},
                "inference": {"inference_id": inference_id, "test_x": test_x, "predicted_class": predicted_class, "raw_values": prediction["values"]},
            }
            print(json.dumps(summary, indent=2))
        finally:
            client.stop_inference(inference_id)
            client.delete_inference(inference_id)


if __name__ == "__main__":
    main()
