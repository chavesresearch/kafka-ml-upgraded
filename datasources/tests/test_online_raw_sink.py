"""Tests for OnlineRawSink - same auto-detect-on-first-send as RawSink,
plus firing the online control message as a side effect of that first
send (the exact behavior model_training/tensorflow/CLAUDE.md's CASE=2
section documents as a real timing gotcha for callers)."""

from conftest import ndarray

from kafkaml_datasources import OnlineRawSink


def _make_sink(**overrides):
    kwargs = dict(boostrap_servers="kafka:9092", topic="data-topic", deployment_id=1)
    kwargs.update(overrides)
    return OnlineRawSink(**kwargs)


def test_first_send_fires_the_online_control_message(patch_kafka):
    sink = _make_sink()
    sink.send(ndarray([1.0]), ndarray([0]))
    producer = sink._KafkaMLSink__producer
    control_sends = [s for s in producer.sent if s["topic"] == "KAFKA_ML_CONTROL_TOPIC"]
    assert len(control_sends) == 1


def test_second_send_does_not_refire_the_control_message(patch_kafka):
    sink = _make_sink()
    sink.send(ndarray([1.0]), ndarray([0]))
    sink.send(ndarray([2.0]), ndarray([1]))
    producer = sink._KafkaMLSink__producer
    control_sends = [s for s in producer.sent if s["topic"] == "KAFKA_ML_CONTROL_TOPIC"]
    assert len(control_sends) == 1


def test_control_message_not_fired_automatically_when_unsupervised_topic_set(patch_kafka):
    """`OnlineRawSink.send()` only auto-fires the control message when
    there's no unsupervised topic - see its own `if self.unsupervised_topic
    is None:` guard. With one set, the caller is expected to trigger it
    itself (e.g. via `send_online_control_msg()` directly)."""
    sink = _make_sink(unsupervised_topic="unsup-topic")
    sink.send(ndarray([1.0]), ndarray([0]))
    producer = sink._KafkaMLSink__producer
    control_sends = [s for s in producer.sent if s["topic"] == "KAFKA_ML_CONTROL_TOPIC"]
    assert control_sends == []


def test_pre_configuring_format_and_calling_send_online_control_msg_skips_autodetect(patch_kafka):
    """The pattern model_training/tensorflow/CLAUDE.md recommends for
    deterministic test timing: pass data_type/label_type/reshape
    explicitly so the sink is "already configured", then call
    send_online_control_msg() directly before any real send()."""
    sink = _make_sink(data_type="float32", label_type="uint8", data_reshape="1", label_reshape="1")
    assert sink._configured_format is True

    sink.send_online_control_msg()
    producer = sink._KafkaMLSink__producer
    assert len([s for s in producer.sent if s["topic"] == "KAFKA_ML_CONTROL_TOPIC"]) == 1

    # A later real send() must not re-fire the control message or
    # overwrite the pre-configured format.
    sink.send(ndarray([1.0]), ndarray([0]))
    assert sink.data_type == "float32"
    assert len([s for s in producer.sent if s["topic"] == "KAFKA_ML_CONTROL_TOPIC"]) == 1
