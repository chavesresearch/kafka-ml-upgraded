"""Shared fakes for kafkaml_datasources tests.

Every Sink class talks to Kafka the moment it's constructed
(`KafkaConsumer`/`KafkaProducer` in `sink.py`'s `__init__`, `KafkaProducer`
in `avro_inference.py`'s), so there's no way to unit-test the pure
encoding/formatting logic these classes wrap without a real broker unless
those two classes are replaced first. `FakeConsumer`/`FakeProducer` below
stand in for them - just enough surface for what this package actually
calls (`partitions_for_topic`, `end_offsets`, `close` on the consumer;
`send`, `flush`, `close` on the producer), recording what was sent instead
of talking to a broker.

A real end-to-end run against an actual Kafka broker was done once
manually (see `../CLAUDE.md`) - this suite is deliberately not trying to
replace that, just to give routine changes here (encoding, control-message
shape, the auto-detect-format-on-first-send logic each Sink subclass
repeats) a fast, broker-free regression check.
"""

from unittest.mock import MagicMock

import pytest


class FakeConsumer:
    """Stand-in for `kafka.KafkaConsumer`."""

    instances: list["FakeConsumer"] = []

    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs
        self.closed_autocommit = None
        FakeConsumer.instances.append(self)

    def partitions_for_topic(self, topic):
        if topic is None:
            return None
        return {0}

    def end_offsets(self, topic_partitions):
        return {tp: 0 for tp in topic_partitions}

    def close(self, autocommit=False):
        self.closed_autocommit = autocommit


class FakeProducer:
    """Stand-in for `kafka.KafkaProducer` - records every `send()` instead
    of writing to a real broker."""

    instances: list["FakeProducer"] = []

    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs
        self.sent: list[dict] = []
        self.flushed = False
        self.closed = False
        FakeProducer.instances.append(self)

    def send(self, topic, value=None, key=None):
        record = {"topic": topic, "key": key, "value": value}
        self.sent.append(record)
        return record

    def flush(self):
        self.flushed = True

    def close(self):
        self.closed = True


@pytest.fixture
def patch_kafka(monkeypatch):
    """Patches every `kafka.KafkaConsumer`/`kafka.KafkaProducer` reference
    this package holds, so constructing any Sink needs no real broker.
    Returns the fake classes so tests can inspect `.instances`."""
    import kafkaml_datasources.avro_inference as avro_inference_mod
    import kafkaml_datasources.sink as sink_mod

    FakeConsumer.instances = []
    FakeProducer.instances = []

    monkeypatch.setattr(sink_mod, "KafkaConsumer", FakeConsumer)
    monkeypatch.setattr(sink_mod, "KafkaProducer", FakeProducer)
    monkeypatch.setattr(avro_inference_mod, "KafkaProducer", FakeProducer)

    return {"consumer": FakeConsumer, "producer": FakeProducer}


class ndarray:  # noqa: N801 - name matters, not styled as a real class
    """Minimal numpy-`ndarray`-shaped stand-in: `shape_to_string`/
    `type_to_string` duck-type on `type(x).__name__` starting with
    `"ndarray"` and on `.shape`/indexing - this avoids a real numpy
    dependency in this package (see ../CLAUDE.md's "Design choices carried
    over unchanged" note) while still exercising that duck-typed path.
    The class is literally named `ndarray` so `type(x).__name__` matches."""

    def __init__(self, values, shape=None):
        self._values = values
        self.shape = shape if shape is not None else (len(values),)

    def __getitem__(self, index):
        return self._values[index]

    def tobytes(self):
        return repr(self._values).encode()
