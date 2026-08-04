---
sidebar_position: 1
---

# kafkaml-client

A Python client for the Kafka-ML backend REST API — create models,
configurations, deployments, and inferences from code instead of
hand-rolling `httpx`/`requests` calls and remembering each endpoint's
exact field names.

:::note Status
This is a draft/proof-of-concept, not a polished, versioned SDK yet. It
covers the core CRUD operations plus the "wait until a real training
result finishes" polling loop that almost every real usage needs — not
the backend's entire surface (datasources, IoT devices, and the
websocket visualization relay aren't wrapped here yet). Every method
returns plain `dict`/`list[dict]` straight from the JSON response, not
typed models.
:::

## Install

```bash
uv add kafkaml-client
# or: pip install kafkaml-client
```

## Usage

```python
from kafkaml_client import KafkaMLClient

MODEL_CODE = '''model = tf.keras.Sequential([
    tf.keras.layers.Input((1,)),
    tf.keras.layers.Dense(10, activation="relu"),
    tf.keras.layers.Dense(2, activation="softmax")
])
model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])
'''

with KafkaMLClient("http://localhost:8000") as client:
    model_id = client.create_model("my-model", MODEL_CODE, framework="tf")
    config_id = client.create_configuration("my-config", [model_id])
    deployment_id = client.create_deployment(
        configuration=config_id,
        batch=4,
        tf_kwargs_fit="epochs=1",
    )

    # ... send training data to Kafka, e.g. with kafkaml-datasources'
    # RawSink(deployment_id=deployment_id, ...) ...

    results = client.wait_for_results(deployment_id, timeout=120)
    print(results[0]["train_metrics"])

    # Real-time inference
    inference_id = client.deploy_inference(
        results[0]["id"], input_topic="my-input", output_topic="my-output",
    )
    # ... later ...
    client.stop_inference(inference_id)
    client.delete_inference(inference_id)
```

## What this wraps

`/models/`, `/configurations/`, `/deployments/`, `/results/`,
`/results/inference/{id}`, `/inferences/{id}` — the same endpoints the
Web UI itself uses.

## Where to go next

- [Creating Models](./creating-models) — single and distributed models
- [Deployments & Training Modes](./deployments-and-training-modes) — every field `create_deployment` accepts, mapped to which training mode it produces
- [Waiting for Results & Inference](./waiting-for-results-and-inference) — polling, timeouts, and real-time inference
- [API Reference](./api-reference) — every method, in full
