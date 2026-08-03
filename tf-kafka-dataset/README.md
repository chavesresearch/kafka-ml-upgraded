# tf-kafka-dataset

`tf.data.Dataset` sources that read directly from Apache Kafka - a
drop-in replacement for `tensorflow-io`'s Kafka dataset ops
(`tensorflow_io.kafka.KafkaDataset`,
`tfio.experimental.streaming.KafkaBatchIODataset`), which haven't shipped
a release since mid-2023 and cap out at TensorFlow 2.16.

## Install

```
uv add tf-kafka-dataset
# or: pip install tf-kafka-dataset
```

## Usage

### Replay a known offset range (bounded)

```python
from tf_kafka_dataset import get_bounded_kafka_dataset

# "topic:partition:start_offset:end_offset", comma-separated for more than one
dataset = get_bounded_kafka_dataset(
    "my-topic:0:0:1000",
    bootstrap_servers="localhost:9092",
    group_id="my-consumer-group",
)
dataset = dataset.map(lambda value, key: (decode(value), decode(key)))
model.fit(dataset.batch(32))
```

### Continuously poll for new data (streaming)

```python
from tf_kafka_dataset import get_streaming_kafka_batches

for mini_dataset in get_streaming_kafka_batches(
    "my-topic",
    bootstrap_servers="localhost:9092",
    group_id="my-consumer-group",
    stream_timeout=60000,  # ms of no new data before this generator stops; -1 = forever
):
    mini_dataset = mini_dataset.map(lambda value, key: (decode(value), decode(key)))
    model.fit(mini_dataset.batch(32))
```

Both yield the same `(value, key)` raw-byte-string pair shape
`tensorflow-io`'s Kafka datasets used to produce, so an existing
`.map(lambda x, y: decode(x, y))` pipeline works unmodified.

## Why not just pin an old TensorFlow + tensorflow-io?

`tensorflow-io`'s last release was mid-2023 and its TensorFlow ceiling is
2.16 - it has no Kafka-reading equivalent for any TensorFlow release
since. This package doesn't try to reproduce `tensorflow-io`'s full
surface (Avro/Parquet/etc. support, other data sources) - just the two
Kafka dataset ops, on top of the actively maintained `kafka-python`
client.

## Status

Extracted from, and used by,
[Kafka-ML](https://github.com/ertis-research/kafka-ml)'s modernized
TensorFlow training containers
(`model_training-upgraded/tensorflow/kafka_dataset.py` and
`federated-module-upgraded/federated_model_training/tensorflow/kafka_dataset.py`
both depend on this package rather than duplicating the code) - but has
no Kafka-ML-specific behavior in it. Useful for any TensorFlow + Kafka
project.
