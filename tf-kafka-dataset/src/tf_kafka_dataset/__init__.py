"""tf.data.Dataset sources that read directly from Apache Kafka.

`tensorflow-io` (the previous way to do this - `tensorflow_io.kafka.KafkaDataset`
and `tfio.experimental.streaming.KafkaBatchIODataset`) hasn't shipped a
release since mid-2023 and caps out at TensorFlow 2.16, so it can't be used
with any current TensorFlow version. This package re-implements both
capabilities on top of the actively maintained `kafka-python` client:

- `get_bounded_kafka_dataset`: replay an exact, already-known offset range
  (or several, across partitions/topics) as a finite `tf.data.Dataset` -
  the `KafkaDataset` replacement.
- `get_streaming_kafka_batches`: continuously poll a topic for new
  messages, yielding one small `tf.data.Dataset` per poll cycle that
  produced data - the `KafkaBatchIODataset` replacement.

Both yield the same shape as the old ops: `(value, key)` byte-string
pairs, so an existing `.map(lambda x, y: decode(x, y))` pipeline built
against `tensorflow-io`'s Kafka datasets works unmodified against these.
"""

from .datasets import get_bounded_kafka_dataset, get_streaming_kafka_batches

__all__ = [
    "get_bounded_kafka_dataset",
    "get_streaming_kafka_batches",
]
