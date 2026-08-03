"""TensorFlow inference deployment - real API + real Kafka.

Trains a real (tiny) model through the same flow as CASE=1, then deploys
it for real-time inference via `POST /results/inference/{result_id}` -
which makes backend-litestar create a real Kubernetes
ReplicationController - sends one raw message to the inference input
topic, and checks a real prediction lands on the output topic.
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
    TF_SINGLE_MODEL_CODE,
    api_client,
    create_configuration,
    create_deployment,
    create_model,
    wait_for_status,
)


def test_tensorflow_inference():
    run_id = uuid.uuid4().hex[:8]

    with api_client() as client:
        model_id = create_model(client, f"it-inf-model-{run_id}", TF_SINGLE_MODEL_CODE, framework="tf")
        config_id = create_configuration(client, f"it-inf-config-{run_id}", [model_id])
        deployment_id = create_deployment(
            client,
            configuration=config_id,
            batch=4,
            tf_kwargs_fit="epochs=1",
            tf_kwargs_val="",
            incremental=False,
            federated=False,
            conf_mat_settings=False,
        )

        topic = f"it-inf-train-data-{run_id}"
        sink = RawSink(
            boostrap_servers=BOOTSTRAP_SERVERS,
            topic=topic,
            deployment_id=deployment_id,
            description="integration-test-inference-training",
            validation_rate=0.2,
            test_rate=0.1,
        )
        rng = np.random.default_rng(6)
        for _ in range(40):
            x = rng.random(1).astype(np.float32)
            y = np.array([int(x[0] > 0.5)], dtype=np.uint8)
            sink.send(x, y)
        sink.close()

        results = wait_for_status(client, deployment_id, "finished")
        result_id = results[0]["id"]

        input_topic = f"it-inf-input-{run_id}"
        output_topic = f"it-inf-output-{run_id}"
        resp = client.post(
            f"/results/inference/{result_id}",
            json={
                "replicas": 1,
                "input_format": "RAW",
                "input_config": json.dumps({"data_type": "float32", "data_reshape": "1"}),
                "input_topic": input_topic,
                "output_topic": output_topic,
                "gpumem": 0,
            },
        )
        assert resp.status_code in (200, 201), f"deploy_inference failed: {resp.status_code} {resp.text}"

        inferences = client.get("/inferences/").json()
        inference_id = next(i["id"] for i in inferences if i["model_result"] == result_id)

        try:
            # Give the ReplicationController's pod time to start, download
            # the trained model, and join its Kafka consumer group.
            time.sleep(20)

            producer = KafkaProducer(bootstrap_servers=BOOTSTRAP_SERVERS)
            producer.send(input_topic, struct.pack("f", 0.7))
            producer.flush()
            producer.close()

            consumer = KafkaConsumer(
                output_topic,
                bootstrap_servers=BOOTSTRAP_SERVERS,
                auto_offset_reset="earliest",
                consumer_timeout_ms=30000,
            )
            prediction = None
            for msg in consumer:
                prediction = json.loads(msg.value.decode("utf-8"))
                break
            consumer.close()

            assert prediction is not None, "no prediction received on the output topic"
            assert "values" in prediction and len(prediction["values"]) == 2
            print(f"Inference OK - inference {inference_id}, prediction: {prediction}")
        finally:
            # Real inference deployments are long-running (a
            # ReplicationController, not a Job) - clean up after the test
            # regardless of outcome.
            client.post(f"/inferences/{inference_id}")
            client.delete(f"/inferences/{inference_id}")


if __name__ == "__main__":
    test_tensorflow_inference()
