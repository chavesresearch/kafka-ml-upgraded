# kafkaml-client

A Python client for the [Kafka-ML](https://github.com/ertis-research/kafka-ml)
backend REST API - create models, configurations, deployments, and
inferences from code instead of hand-rolling `httpx`/`requests` calls and
remembering each endpoint's exact field names.

## Install

```
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

Distributed models: pass `father=<root_model_id>` when creating a child
node's model, and only the root model's id to `create_configuration` -
the backend expands the father/child chain automatically.

## What this wraps

`/models/`, `/configurations/`, `/deployments/`, `/results/`,
`/results/inference/{id}`, `/inferences/{id}` - the same endpoints a
frontend uses. See `client.py`'s docstrings for the full field reference
per endpoint (in particular `create_deployment`'s `**fields` - TensorFlow
vs. PyTorch kwargs use different key names, and incremental/distributed/
federated deployments each need their own extra fields).

## Status

A draft/proof-of-concept, not a polished, versioned SDK. Built by lifting
the request-building/polling logic that
[Kafka-ML](https://github.com/ertis-research/kafka-ml)'s own
`integration-tests/` suite needed anyway (see that directory's
`common.py`, which now just re-exports from this package) - covers the
core CRUD + the "wait until a real training result finishes" polling loop
that almost every real usage needs, not the backend's entire surface
(datasources, IoT devices, websocket visualization, etc. aren't wrapped
here yet).
