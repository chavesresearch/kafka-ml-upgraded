"""Tests for FederatedRawSink - same auto-detect-on-first-send shape as
RawSink, but defaults control_topic to FEDERATED_DATA_CONTROL_TOPIC and
dataset_restrictions to the JSON-encoded string '{}' (not a native dict -
see federated-module/CLAUDE.md's "false alarm" note about this exact
wire-format distinction)."""

from conftest import ndarray

from kafkaml_datasources import FederatedRawSink


def _make_sink(**overrides):
    kwargs = dict(boostrap_servers="kafka:9092", topic="data-topic", deployment_id=1)
    kwargs.update(overrides)
    return FederatedRawSink(**kwargs)


def test_defaults_target_the_federated_control_topic(patch_kafka):
    sink = _make_sink()
    assert sink.control_topic == "FEDERATED_DATA_CONTROL_TOPIC"


def test_dataset_restrictions_default_to_the_json_encoded_string(patch_kafka):
    """Not a native `{}` dict - the real wire format is always a
    JSON-encoded *string*, which federated_backend's check_colission()
    json.loads()s on the receiving end."""
    sink = _make_sink()
    assert sink.dataset_restrictions == "{}"
    assert isinstance(sink.dataset_restrictions, str)


def test_first_send_autodetects_format(patch_kafka):
    sink = _make_sink()
    sink.send(ndarray([1.0]), ndarray([0]))
    assert sink._configured_format is True
    assert sink.data_type == "float"


def test_control_message_carries_the_json_string_restrictions_through(patch_kafka):
    import json

    sink = _make_sink(dataset_restrictions='{"min_data": 100}')
    sink.send_control_msg()
    producer = sink._KafkaMLSink__producer
    payload = json.loads(producer.sent[-1]["value"])
    # The outer control message is JSON; dataset_restrictions inside it
    # stays a string (double-encoded), matching the real wire format.
    assert payload["dataset_restrictions"] == '{"min_data": 100}'
