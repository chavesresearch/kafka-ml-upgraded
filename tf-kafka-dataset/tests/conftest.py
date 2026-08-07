"""Broker-free fakes for tf_kafka_dataset tests.

Both `get_bounded_kafka_dataset` and `get_streaming_kafka_batches`
construct a real `kafka.KafkaConsumer` the moment they're iterated, so -
same reasoning as `../../datasources/tests/conftest.py` - a fake consumer
replaces it, recording just enough real `kafka-python` surface (`assign`,
`seek`, iteration, `poll`, `close`) to drive both code paths without a
real broker.
"""

from collections import namedtuple

import pytest

FakeMessage = namedtuple("FakeMessage", ["value", "key", "offset"])


class FakeBoundedConsumer:
    """Stands in for the `assign()`/`seek()`/iterate pattern
    `_iter_bounded_partition` uses. `topic_messages` maps
    `(topic, partition)` -> a list of `FakeMessage`, indexed by offset."""

    def __init__(self, topic_messages):
        self.topic_messages = topic_messages
        self.assigned = None
        self.sought = None
        self.closed = False

    def __call__(self, *args, **kwargs):
        # kafka.KafkaConsumer is referenced as a class and instantiated
        # fresh per partition read - this fake's __call__ makes one
        # `FakeBoundedConsumer(...)` instance behave like the *class*
        # tf_kafka_dataset imports, while still sharing the same
        # `topic_messages` fixture data across every constructed instance.
        return _FakeBoundedConsumerInstance(self.topic_messages)


class _FakeBoundedConsumerInstance:
    def __init__(self, topic_messages):
        self.topic_messages = topic_messages
        self.assigned = None
        self.start_offset = None
        self.closed = False

    def assign(self, topic_partitions):
        self.assigned = topic_partitions[0]

    def seek(self, tp, offset):
        self.start_offset = offset

    def __iter__(self):
        key = (self.assigned.topic, self.assigned.partition)
        messages = self.topic_messages.get(key, [])
        for msg in messages[self.start_offset:]:
            yield msg

    def close(self):
        self.closed = True


class FakeStreamingConsumer:
    """Stands in for the `poll()`-based streaming consumer.

    `get_streaming_kafka_batches` is itself a generator function, so the
    real `KafkaConsumer` isn't constructed until the *first* `next()` call
    on it - there's no instance to configure beforehand. `pending_poll_results`
    is a class-level list a test sets before ever calling `next()`; each
    new instance snapshots it as its own `poll_results` at construction
    time. `poll_results` is a list of `{TopicPartition: [FakeMessage,
    ...]}` dicts, one per `poll()` call, in order - any call beyond the
    list's length gets an empty dict, so a test doesn't need to predict
    the exact call count."""

    instances: list["FakeStreamingConsumer"] = []
    pending_poll_results: list[dict] = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.poll_results = list(FakeStreamingConsumer.pending_poll_results)
        self._poll_call = 0
        self.closed = False
        FakeStreamingConsumer.instances.append(self)

    def poll(self, timeout_ms=None):
        if self._poll_call < len(self.poll_results):
            result = self.poll_results[self._poll_call]
        else:
            result = {}
        self._poll_call += 1
        return result

    def close(self):
        self.closed = True


@pytest.fixture
def fake_bounded_consumer(monkeypatch):
    """Patches `tf_kafka_dataset.datasets.KafkaConsumer` for
    `get_bounded_kafka_dataset` tests. Returns a function to register
    `(topic, partition) -> [FakeMessage, ...]` data before the dataset is
    iterated."""
    import tf_kafka_dataset.datasets as datasets_mod

    topic_messages: dict[tuple[str, int], list[FakeMessage]] = {}
    fake_cls = FakeBoundedConsumer(topic_messages)
    monkeypatch.setattr(datasets_mod, "KafkaConsumer", fake_cls)

    def register(topic, partition, messages):
        topic_messages[(topic, partition)] = messages

    return register


@pytest.fixture
def fake_streaming_consumer(monkeypatch):
    """Patches `tf_kafka_dataset.datasets.KafkaConsumer` for
    `get_streaming_kafka_batches` tests. Returns `FakeStreamingConsumer`
    so a test can set `.poll_results` on the instance created inside the
    generator (via `FakeStreamingConsumer.instances[-1]`, since the
    generator constructs it lazily on first iteration)."""
    import tf_kafka_dataset.datasets as datasets_mod

    FakeStreamingConsumer.instances = []
    FakeStreamingConsumer.pending_poll_results = []
    monkeypatch.setattr(datasets_mod, "KafkaConsumer", FakeStreamingConsumer)
    return FakeStreamingConsumer
