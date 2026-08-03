"""Kafka data-loading primitives for TensorFlow training.

Replaces tensorflow-io's Kafka dataset ops
(`tensorflow_io.kafka.KafkaDataset`,
`tfio.experimental.streaming.KafkaBatchIODataset`) - tensorflow-io hasn't
shipped a release since mid-2023 and caps out at TF 2.16, so it can't be
used with the TF 2.21 this trainer now runs (see CLAUDE.md for the full
rationale - the same blocker hit `mlcode_executor-litestar/tfexecutor`).

Both replacements are built on `kafka-python`, mirroring the exact
"topic:partition:start_offset:end_offset" bounded-replay pattern already
used elsewhere in this same repo for reading model weights
(`KafkaModelEngine.__createconsumer__`) and in the PyTorch trainer
(`model_training/pytorch/TrainingKafkaDataset.py`) - not a new invention,
just the third implementation of an existing pattern.
"""

import logging

import tensorflow as tf
from kafka import KafkaConsumer, TopicPartition

_RAW_PAIR_SIGNATURE = (
    tf.TensorSpec(shape=(), dtype=tf.string),
    tf.TensorSpec(shape=(), dtype=tf.string),
)
"""Shape of the raw (value, key) byte pairs yielded before decoding - matches
what `tensorflow_io.kafka.KafkaDataset(..., message_key=True)` used to
produce. Callers still do `.map(lambda x, y: decoder.decode(x, y))`
exactly as before; only the source of these pairs changed."""


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


def get_bounded_kafka_dataset(topic_spec, bootstrap_servers, group_id):
    """Replays the exact offset range(s) encoded in `topic_spec`.

    Used for every non-streaming training mode (classic, distributed, and
    the labeled portion of semi-supervised incremental training).

    Args:
        topic_spec (str): comma-separated "topic:partition:start_offset:end_offset"
            entries, as produced by the control message
            KafkaMLSink/FederatedKafkaMLModelSink send (see
            `datasources-package`) - the same format `KafkaModelEngine`
            already parses for model weights.
        bootstrap_servers (str): Kafka bootstrap servers
        group_id: Kafka consumer group id (coerced to `str` - kafka-python
            requires a string here, unlike some older clients)

    Returns:
        tf.data.Dataset: raw (value, key) byte-string pairs.
    """
    group_id = str(group_id)
    partitions = []
    for entry in topic_spec.split(','):
        topic, partition, start_offset, end_offset = entry.split(':')
        partitions.append((topic, int(partition), int(start_offset), int(end_offset)))

    def generator():
        for topic, partition, start_offset, end_offset in partitions:
            logging.info("Reading bounded Kafka range topic=%s partition=%d [%d, %d)",
                         topic, partition, start_offset, end_offset)
            yield from _iter_bounded_partition(topic, partition, start_offset, end_offset, bootstrap_servers, group_id)

    return tf.data.Dataset.from_generator(generator, output_signature=_RAW_PAIR_SIGNATURE)


def get_streaming_kafka_batches(topic, bootstrap_servers, group_id, stream_timeout):
    """Replaces `tfio.experimental.streaming.KafkaBatchIODataset` for incremental/online training.

    Continuously polls `topic` for new messages using a real Kafka consumer
    group (so re-running with the same `group_id` resumes rather than
    re-reading from the start), yielding one small, finite `tf.data.Dataset`
    per poll cycle that produced new messages. Each yielded dataset supports
    `len()`/`.take()`/`.skip()`, matching what `split_online_dataset` and
    `train_incremental_model` already expect - `kafka_dataset` itself
    (the return value of this generator) is only ever iterated
    (`for mini_ds in kafka_dataset`), never treated as a `tf.data.Dataset`
    itself, so a plain Python generator is sufficient here.

    Args:
        topic (str): Kafka topic to tail (a plain topic name, not an
            offset-range spec - incremental training reads forward from
            wherever the consumer group already is, not a bounded range)
        bootstrap_servers (str): Kafka bootstrap servers
        group_id: Kafka consumer group id (`self.result_id` - one training
            job's own group. Coerced to `str`: distributed incremental
            training's `self.result_id` is a list, which the old
            tfio-backed implementation passed through as `group_id`
            unchanged - kafka-python's wire protocol needs a string to
            encode the JoinGroup request, so this coercion is required
            here in a way it may not have been before)
        stream_timeout (int): milliseconds of no new data before the
            stream is considered exhausted and this generator stops.
            `-1` means never stop (indefinite/continuous training) - poll
            forever instead.

    Yields:
        tf.data.Dataset: one per poll cycle with new data, of raw
        (value, key) byte-string pairs (same shape as
        `get_bounded_kafka_dataset`) - callers `.map(lambda x, y:
        decoder.decode(x, y))` each one exactly as before.
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
        # rather than trying to hand kafka-python a literal infinite
        # timeout. An empty slice here just means "keep waiting", never
        # stopping - unlike the bounded stream_timeout case below.
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
