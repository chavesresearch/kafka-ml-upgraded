---
sidebar_position: 4
---

# Sending Datasets

Registering a datasource doesn't go through the REST API at all — it
happens over Kafka itself. `send_dataset`/`send_dataframe` need the
`datasets` extra:

```bash
uv add "kafkaml-client[datasets]"
# or: pip install "kafkaml-client[datasets]"
```

## A numpy dataset

```python
import numpy as np

X = np.random.rand(1000, 28, 28).astype("float32")
y = np.random.randint(0, 10, size=1000).astype("uint8")

client.send_dataset(
    "localhost:9094",           # Kafka bootstrap servers - not the backend's base_url
    topic="my-topic",
    deployment_id=deployment_id,
    data=X,
    labels=y,
    validation_rate=0.1,
    test_rate=0.1,
)
```

Row `i` of `data` is paired with row `i` of `labels`, same as the
parallel-iteration pattern every `examples/*/*_dataset_training_example.py`
script in the main repo uses by hand. Format (dtype, shape) is
auto-detected from the first row, same as leaving `RawSink`'s own
`data_type`/`data_reshape` unset.

`data`/`labels` also accept a pandas `Series` or `DataFrame` directly —
converted internally via `.to_numpy()`.

## A pandas DataFrame

If features and label live in one table, `send_dataframe` splits
`label_column` off for you:

```python
import pandas as pd

df = pd.read_csv("training-data.csv")

client.send_dataframe(
    "localhost:9094",
    topic="my-topic",
    deployment_id=deployment_id,
    dataframe=df,
    label_column="target",
)
```

## What actually happens

Both functions build a `kafkaml_datasources.RawSink`, send every row,
then `.close()` it — `.close()` is what publishes the control-topic
message `kafka_control_logger` forwards to the backend, which is what
actually creates the `Datasource` row. There's no separate "register"
call to make.

If `data` and `labels` have different lengths, this is caught **before**
any Kafka client is even constructed — `send_dataset` raises `ValueError`
immediately rather than failing partway through a real send. If a
row-level send does fail mid-stream for some other reason, the sink is
still `.close()`d (from a `finally` block), so a partial send is still
registered with however many rows actually made it through, instead of
leaving already-published data completely unregistered.

## Where the deployment id comes from

`deployment_id` has to already exist — create it the normal way first:

```python
deployment_id = client.create_deployment(configuration=config_id, batch=4, tf_kwargs_fit="epochs=5")
client.send_dataset("localhost:9094", topic="my-topic", deployment_id=deployment_id, data=X, labels=y)
results = client.wait_for_results(deployment_id, timeout=120)
```

See [Deployments & Training Modes](./deployments-and-training-modes) for
every field `create_deployment` accepts.

## Reading predictions back

Once a trained result is deployed for real-time inference, `predict_one`/
`predict_batch` send input row(s) and read the prediction(s) back the
same way — see [Waiting for Results & Inference](./waiting-for-results-and-inference#sending-requests-and-reading-predictions).
