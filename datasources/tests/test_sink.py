"""Tests for KafkaMLSink - the shared base class every other Sink in this
package builds on."""

import json

import pytest
from conftest import ndarray

from kafkaml_datasources.sink import KafkaMLSink


def _make_sink(**overrides):
    kwargs = dict(
        boostrap_servers="kafka:9092",
        topic="data-topic",
        deployment_id=1,
        input_format="RAW",
    )
    kwargs.update(overrides)
    return KafkaMLSink(**kwargs)


def test_init_reads_partitions_for_the_topic(patch_kafka):
    sink = _make_sink()
    assert sink._KafkaMLSink__partitions == {0: {"offset": 0}}


def test_init_leaves_unsupervised_partitions_empty_when_no_unsupervised_topic(patch_kafka):
    sink = _make_sink()
    assert sink._KafkaMLSink__unsupervised_partitions == {}


def test_init_reads_unsupervised_partitions_when_topic_given(patch_kafka):
    sink = _make_sink(unsupervised_topic="unsup-topic")
    assert sink._KafkaMLSink__unsupervised_partitions == {0: {"offset": 0}}


def test_empty_string_unsupervised_topic_is_treated_as_none(patch_kafka):
    sink = _make_sink(unsupervised_topic="")
    assert sink.unsupervised_topic is None


@pytest.mark.parametrize(
    "label,expected",
    [
        (1, b"\x01"),
        (True, b"\x01"),
        (False, b"\x00"),
        ("x", b"x"),
        (b"raw", b"raw"),
    ],
)
def test_send_encodes_supported_label_types(patch_kafka, label, expected):
    sink = _make_sink()
    sink.send(b"data", label)
    producer = sink._KafkaMLSink__producer
    assert producer.sent[-1]["key"] == expected
    assert producer.sent[-1]["value"] == b"data"


def test_send_with_none_label_sends_value_only_no_key(patch_kafka):
    sink = _make_sink()
    sink.send_value(b"data")
    producer = sink._KafkaMLSink__producer
    assert producer.sent[-1]["key"] is None
    assert producer.sent[-1]["value"] == b"data"


def test_send_unsupported_label_type_raises(patch_kafka):
    sink = _make_sink()
    with pytest.raises(Exception, match="Type not supported"):
        sink.send(b"data", {"not": "supported"})


def test_deployment_id_key_survives_ids_above_255(patch_kafka):
    """Regression test: the original single-byte `bytes([deployment_id])`
    encoding raised ValueError for any id >= 256 - see
    KafkaMLSink.__deployment_id_to_bytes' docstring and ../CLAUDE.md."""
    sink = _make_sink(deployment_id=300)
    sink.send_control_msg()
    producer = sink._KafkaMLSink__producer
    key = producer.sent[-1]["key"]
    assert int.from_bytes(key, byteorder="big") == 300


def test_send_control_msg_payload_shape(patch_kafka):
    sink = _make_sink(deployment_id=1, description="desc", validation_rate=0.2, test_rate=0.1)
    sink.send_control_msg()
    producer = sink._KafkaMLSink__producer
    payload = json.loads(producer.sent[-1]["value"])
    assert payload["description"] == "desc"
    assert payload["validation_rate"] == 0.2
    assert payload["test_rate"] == 0.1
    assert payload["input_format"] == "RAW"
    assert payload["incremental"] is False
    assert producer.flushed is True


def test_send_online_control_msg_marks_incremental_true(patch_kafka):
    sink = _make_sink()
    sink.send_online_control_msg()
    producer = sink._KafkaMLSink__producer
    payload = json.loads(producer.sent[-1]["value"])
    assert payload["incremental"] is True


def test_close_flushes_and_closes_both_clients(patch_kafka):
    sink = _make_sink()
    sink.close()
    producer = sink._KafkaMLSink__producer
    consumer = sink._KafkaMLSink__consumer
    assert producer.flushed is True
    assert producer.closed is True
    assert consumer.closed_autocommit is False


def test_online_close_does_not_send_control_message(patch_kafka):
    sink = _make_sink()
    sink.online_close()
    producer = sink._KafkaMLSink__producer
    assert producer.sent == []
    assert producer.flushed is True
    assert producer.closed is True


@pytest.mark.parametrize(
    "shape_input,expected",
    [
        ([1, 2, 3], "3"),  # a plain list -> its length
        ("scalar", "1"),  # anything else -> '1'
    ],
)
def test_shape_to_string_non_array_inputs(patch_kafka, shape_input, expected):
    sink = _make_sink()
    assert sink.shape_to_string(shape_input) == expected


def test_shape_to_string_ndarray_like_input(patch_kafka):
    sink = _make_sink()
    arr = ndarray([1.0], shape=(1,))
    assert sink.shape_to_string(arr) == "1"


def test_type_to_string_drills_into_ndarray_like_input(patch_kafka):
    sink = _make_sink()
    arr = ndarray([1.5])
    assert sink.type_to_string(arr) == "float"


def test_type_to_string_plain_scalar(patch_kafka):
    sink = _make_sink()
    assert sink.type_to_string(1) == "int"
    assert sink.type_to_string("x") == "str"
