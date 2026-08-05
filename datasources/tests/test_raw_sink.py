"""Tests for RawSink - auto-detects data_type/label_type/reshape from the
first send() call unless given explicitly."""

from conftest import ndarray

from kafkaml_datasources import RawSink


def _make_sink(**overrides):
    kwargs = dict(boostrap_servers="kafka:9092", topic="data-topic", deployment_id=1)
    kwargs.update(overrides)
    return RawSink(**kwargs)


def test_explicit_format_is_used_as_is(patch_kafka):
    sink = _make_sink(data_type="uint8", label_type="uint8", data_reshape="28 28", label_reshape="")
    assert sink._configured_format is True
    assert sink.input_config == {
        "data_type": "uint8",
        "label_type": "uint8",
        "data_reshape": "28 28",
        "label_reshape": "",
    }


def test_first_send_autodetects_format_from_the_data(patch_kafka):
    sink = _make_sink()
    assert sink._configured_format is False

    x = ndarray([1.0], shape=(1,))
    y = ndarray([0], shape=(1,))
    sink.send(x, y)

    assert sink._configured_format is True
    assert sink.data_type == "float"
    assert sink.label_type == "int"
    assert sink.data_reshape == "1"
    assert sink.label_reshape == "1"


def test_format_is_only_computed_once(patch_kafka):
    sink = _make_sink()
    sink.send(ndarray([1.0]), ndarray([0]))
    sink.data_type = "sentinel"  # would be overwritten if send() re-ran auto-detect
    sink.send(ndarray([2.0]), ndarray([1]))
    assert sink.data_type == "sentinel"


def test_send_forwards_raw_bytes_to_the_producer(patch_kafka):
    sink = _make_sink(data_type="float", label_type="int", data_reshape="1", label_reshape="1")
    x = ndarray([1.0])
    y = ndarray([0])
    sink.send(x, y)
    producer = sink._KafkaMLSink__producer
    assert producer.sent[-1]["value"] == x.tobytes()
    assert producer.sent[-1]["key"] == y.tobytes()


def test_unsupervised_send_forwards_raw_bytes(patch_kafka):
    sink = _make_sink(unsupervised_topic="unsup-topic")
    x = ndarray([1.0])
    sink.unsupervised_send(x)
    producer = sink._KafkaMLSink__producer
    assert producer.sent[-1]["topic"] == "unsup-topic"
    assert producer.sent[-1]["value"] == x.tobytes()
