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

Add the `datasets` extra to also send numpy/pandas datasets to Kafka and
register them as datasources (`client.send_dataset`/`.send_dataframe` -
see Usage below):

```
uv add "kafkaml-client[datasets]"
# or: pip install "kafkaml-client[datasets]"
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

    # Sends a numpy/pandas dataset to Kafka and registers it as a
    # datasource for this deployment - needs `pip install
    # kafkaml-client[datasets]`.
    import numpy as np
    X = np.random.rand(100, 1).astype("float32")
    y = (X[:, 0] > 0.5).astype("uint8")
    client.send_dataset("localhost:9094", topic="my-topic", deployment_id=deployment_id, data=X, labels=y)

    results = client.wait_for_results(deployment_id, timeout=120)
    print(results[0]["train_metrics"])

    # Real-time inference
    inference_id = client.deploy_inference(
        results[0]["id"], input_topic="my-input", output_topic="my-output",
    )
    # Sends one row and reads its prediction back - also needs the
    # `datasets` extra.
    prediction = client.predict_one("localhost:9094", "my-input", "my-output", X[0])
    # For several rows at once, in order: client.predict_batch(..., rows)
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

Datasource registration itself happens over Kafka, not this REST API (see
`kafkaml_client/datasets.py`) - `send_dataset`/`send_dataframe` (needs the
`datasets` extra) send a numpy/pandas dataset to Kafka directly and
register it automatically, the same flow this project's own
`examples/*/*_dataset_training_example.py` scripts hand-roll with
`kafkaml_datasources.RawSink`. Real-time inference request/response is
the same story on the other end (see `kafkaml_client/predictions.py`) -
`predict_one`/`predict_batch` (also needs the `datasets` extra) send
input row(s) to a deployed inference's input topic and read the
prediction(s) back, the same flow `examples/*/*_dataset_inference_example.py`
scripts hand-roll with plain `kafka.KafkaProducer`/`KafkaConsumer`. Its
output consumer always reads from `"earliest"`, not `kafka-python`'s own
`"latest"` default - a consumer created with the default can join its
group after a fast deployment has already produced the prediction and
silently see nothing, a real bug found (and fixed, in 6 places) in this
project's own examples while building this.

## Status

A draft/proof-of-concept, not a polished, versioned SDK. Built by lifting
the request-building/polling logic that
[Kafka-ML](https://github.com/ertis-research/kafka-ml)'s own
`integration-tests/` suite needed anyway (see that directory's
`common.py`, which now just re-exports from this package) - covers the
core CRUD + the "wait until a real training result finishes" polling loop
that almost every real usage needs, plus (with the `datasets` extra)
sending a dataset to Kafka and registering it, and sending/reading
real-time inference requests. Not the backend's entire surface though -
IoT devices and websocket visualization aren't wrapped here yet.
