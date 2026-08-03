import logging

import tensorflow as tf
from kafka import KafkaConsumer, TopicPartition

_RAW_PAIR_SIGNATURE = (
    tf.TensorSpec(shape=(), dtype=tf.string),
    tf.TensorSpec(shape=(), dtype=tf.string),
)
"""Shape of the raw (value, key) byte pairs yielded before decoding -
matches what `tensorflow_io.kafka.KafkaDataset(..., message_key=True)`
used to produce."""


def _iter_bounded_partition(topic, partition, start_offset, end_offset, bootstrap_servers, group_id):
    """Yields (value, key) byte pairs for one partition's [start_offset, end_offset) range."""
    consumer = KafkaConsumer(
        bootstrap_servers=bootstrap_servers,
        enable_auto_commit=False,
        group_id=group_id,
    )
    try:
        tp = TopicPartition(topic, partition)
        consumer.assign([tp])
        consumer.seek(tp, start_offset)

        for message in consumer:
            yield message.value, message.key
            if message.offset >= end_offset - 1:
                break
    finally:
        consumer.close()


def get_bounded_kafka_dataset(topic_spec: str, bootstrap_servers: str, group_id) -> tf.data.Dataset:
    """Replays the exact offset range(s) encoded in `topic_spec`.

    Args:
        topic_spec: comma-separated ``"topic:partition:start_offset:end_offset"``
            entries (e.g. ``"my-topic:0:0:100"``, or
            ``"my-topic:0:0:100,my-topic:1:0:100"`` for multiple
            partitions/topics in one dataset).
        bootstrap_servers: Kafka bootstrap servers.
        group_id: Kafka consumer group id (coerced to `str` - kafka-python
            requires a string here, unlike some older clients).

    Returns:
        A `tf.data.Dataset` of raw `(value, key)` byte-string pairs, in
        offset order. `.assign()` + `.seek()` are used rather than
        `.subscribe()` - this reads a known, fixed range, so there's no
        need for (and no wait on) consumer-group rebalancing.
    """
    group_id = str(group_id)
    partitions = []
    for entry in topic_spec.split(","):
        topic, partition, start_offset, end_offset = entry.split(":")
        partitions.append((topic, int(partition), int(start_offset), int(end_offset)))

    def generator():
        for topic, partition, start_offset, end_offset in partitions:
            logging.info(
                "Reading bounded Kafka range topic=%s partition=%d [%d, %d)",
                topic, partition, start_offset, end_offset,
            )
            yield from _iter_bounded_partition(topic, partition, start_offset, end_offset, bootstrap_servers, group_id)

    return tf.data.Dataset.from_generator(generator, output_signature=_RAW_PAIR_SIGNATURE)


def get_streaming_kafka_batches(topic: str, bootstrap_servers: str, group_id, stream_timeout: int):
    """Continuously polls `topic` for new messages, yielding one small,
    finite `tf.data.Dataset` per poll cycle that produced new messages.

    This is a generator, not a `tf.data.Dataset` itself - iterate it
    directly (`for mini_ds in get_streaming_kafka_batches(...): ...`),
    consuming each yielded `mini_ds` as its own small dataset (it
    supports `len()`/`.take()`/`.skip()`/`.batch()` like any other
    in-memory `tf.data.Dataset`).

    Args:
        topic: a plain Kafka topic name (not an offset-range spec - this
            reads forward from wherever the consumer group already is,
            not a bounded range).
        bootstrap_servers: Kafka bootstrap servers.
        group_id: Kafka consumer group id - this client's own group, so
            re-running with the same `group_id` resumes rather than
            re-reading from the start. Coerced to `str`.
        stream_timeout: milliseconds of no new data before the stream is
            considered exhausted and this generator stops. `-1` means
            never stop - poll forever (useful for continuous/indefinite
            training loops).

    Yields:
        `tf.data.Dataset` instances of raw `(value, key)` byte-string
        pairs (same shape as `get_bounded_kafka_dataset`), one per poll
        cycle that produced new messages.
    """
    group_id = str(group_id)
    consumer = KafkaConsumer(
        topic,
        bootstrap_servers=bootstrap_servers,
        enable_auto_commit=False,
        group_id=group_id,
    )
    try:
        # When polling "forever" (-1), still poll in finite slices so an
        # empty slice can be checked against stream_timeout in a loop,
        # rather than handing kafka-python a literal infinite timeout.
        poll_timeout_ms = stream_timeout if stream_timeout != -1 else 60000

        while True:
            records = consumer.poll(timeout_ms=poll_timeout_ms)
            messages = [msg for partition_msgs in records.values() for msg in partition_msgs]

            if not messages:
                if stream_timeout == -1:
                    continue
                logging.info("No new data for %d ms, stream considered exhausted", stream_timeout)
                return

            values = [msg.value for msg in messages]
            keys = [msg.key for msg in messages]
            logging.info("Received %d new message(s) from topic %s", len(messages), topic)

            yield tf.data.Dataset.from_tensor_slices((values, keys))
    finally:
        consumer.close()
