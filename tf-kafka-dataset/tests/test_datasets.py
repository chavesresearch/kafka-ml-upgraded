"""Real `tf.data.Dataset` tests for both sources this package provides -
`kafka.KafkaConsumer` is faked (see conftest.py), but the dataset objects
themselves are real, actually-iterated `tf.data.Dataset`s, not mocks - this
proves the generator functions actually produce the shape/values TensorFlow
expects, not just that the right consumer calls happened.
"""

from kafka import TopicPartition

from tf_kafka_dataset import get_bounded_kafka_dataset, get_streaming_kafka_batches

from conftest import FakeMessage


def _msgs(*values, key=b""):
    return [FakeMessage(value=v, key=key, offset=i) for i, v in enumerate(values)]


class TestGetBoundedKafkaDataset:
    def test_yields_exact_offset_range(self, fake_bounded_consumer):
        fake_bounded_consumer("t", 0, _msgs(b"v0", b"v1", b"v2", b"v3", b"v4"))

        ds = get_bounded_kafka_dataset("t:0:0:3", bootstrap_servers="x", group_id=1)

        assert list(ds.as_numpy_iterator()) == [(b"v0", b""), (b"v1", b""), (b"v2", b"")]

    def test_respects_a_nonzero_start_offset(self, fake_bounded_consumer):
        fake_bounded_consumer("t", 0, _msgs(b"v0", b"v1", b"v2", b"v3", b"v4"))

        ds = get_bounded_kafka_dataset("t:0:2:4", bootstrap_servers="x", group_id=1)

        values = [v for v, _ in ds.as_numpy_iterator()]
        assert values == [b"v2", b"v3"]

    def test_multiple_partitions_are_concatenated_in_spec_order(self, fake_bounded_consumer):
        fake_bounded_consumer("t", 0, _msgs(b"a0"))
        fake_bounded_consumer("t", 1, _msgs(b"b0"))

        ds = get_bounded_kafka_dataset("t:0:0:1,t:1:0:1", bootstrap_servers="x", group_id=1)

        values = [v for v, _ in ds.as_numpy_iterator()]
        assert values == [b"a0", b"b0"]

    def test_multiple_topics_in_one_spec(self, fake_bounded_consumer):
        fake_bounded_consumer("topic-a", 0, _msgs(b"a0"))
        fake_bounded_consumer("topic-b", 0, _msgs(b"b0"))

        ds = get_bounded_kafka_dataset("topic-a:0:0:1,topic-b:0:0:1", bootstrap_servers="x", group_id=1)

        values = [v for v, _ in ds.as_numpy_iterator()]
        assert values == [b"a0", b"b0"]

    def test_preserves_keys_alongside_values(self, fake_bounded_consumer):
        fake_bounded_consumer(
            "t", 0, [FakeMessage(value=b"v0", key=b"k0", offset=0), FakeMessage(value=b"v1", key=b"k1", offset=1)]
        )

        ds = get_bounded_kafka_dataset("t:0:0:2", bootstrap_servers="x", group_id=1)

        assert list(ds.as_numpy_iterator()) == [(b"v0", b"k0"), (b"v1", b"k1")]

    def test_group_id_is_coerced_to_str(self, fake_bounded_consumer):
        # group_id=1 (an int) must not raise when passed through to a real
        # KafkaConsumer, which requires a string - covers the `str(group_id)`
        # coercion `get_bounded_kafka_dataset` does up front.
        fake_bounded_consumer("t", 0, _msgs(b"v0"))

        ds = get_bounded_kafka_dataset("t:0:0:1", bootstrap_servers="x", group_id=1)

        assert list(ds.as_numpy_iterator()) == [(b"v0", b"")]


class TestGetStreamingKafkaBatches:
    def test_yields_one_dataset_per_poll_that_has_messages(self, fake_streaming_consumer):
        tp = TopicPartition("t", 0)
        fake_streaming_consumer.pending_poll_results = [
            {tp: [FakeMessage(value=b"v1", key=b"k1", offset=0), FakeMessage(value=b"v2", key=b"k2", offset=1)]},
            {},  # empty poll with a finite stream_timeout -> stream ends here
        ]

        results = list(get_streaming_kafka_batches("t", bootstrap_servers="x", group_id=1, stream_timeout=500))

        assert len(results) == 1
        assert list(results[0].as_numpy_iterator()) == [(b"v1", b"k1"), (b"v2", b"k2")]

    def test_stops_after_an_empty_poll_when_stream_timeout_is_finite(self, fake_streaming_consumer):
        fake_streaming_consumer.pending_poll_results = [{}]

        results = list(get_streaming_kafka_batches("t", bootstrap_servers="x", group_id=1, stream_timeout=100))

        assert results == []
        assert fake_streaming_consumer.instances[-1].closed is True

    def test_infinite_timeout_keeps_polling_through_empty_polls(self, fake_streaming_consumer):
        tp = TopicPartition("t", 0)
        fake_streaming_consumer.pending_poll_results = [
            {},
            {},
            {tp: [FakeMessage(value=b"v", key=b"k", offset=0)]},
        ]

        gen = get_streaming_kafka_batches("t", bootstrap_servers="x", group_id=1, stream_timeout=-1)
        ds = next(gen)

        assert list(ds.as_numpy_iterator()) == [(b"v", b"k")]
        # 3 poll() calls: two empty ones it kept going through, plus the one
        # that finally produced data - proves stream_timeout=-1 never gives
        # up on an empty poll the way a finite timeout does above.
        assert fake_streaming_consumer.instances[-1]._poll_call == 3

    def test_closes_the_consumer_once_the_generator_is_exhausted(self, fake_streaming_consumer):
        tp = TopicPartition("t", 0)
        fake_streaming_consumer.pending_poll_results = [
            {tp: [FakeMessage(value=b"v", key=b"k", offset=0)]},
            {},
        ]

        list(get_streaming_kafka_batches("t", bootstrap_servers="x", group_id=1, stream_timeout=100))

        assert fake_streaming_consumer.instances[-1].closed is True

    def test_group_id_is_coerced_to_str(self, fake_streaming_consumer):
        fake_streaming_consumer.pending_poll_results = [{}]

        list(get_streaming_kafka_batches("t", bootstrap_servers="x", group_id=42, stream_timeout=100))

        assert fake_streaming_consumer.instances[-1].kwargs["group_id"] == "42"
