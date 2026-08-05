"""Tests for OnlineFederatedRawSink - unlike OnlineRawSink, this one never
auto-detects the format on first send(); callers must call
send_online_control_msg(data, label) themselves with a sample."""

from conftest import ndarray

from kafkaml_datasources import OnlineFederatedRawSink


def _make_sink(**overrides):
    kwargs = dict(boostrap_servers="kafka:9092", topic="data-topic", deployment_id=1)
    kwargs.update(overrides)
    return OnlineFederatedRawSink(**kwargs)


def test_defaults_target_the_federated_control_topic(patch_kafka):
    sink = _make_sink()
    assert sink.control_topic == "FEDERATED_DATA_CONTROL_TOPIC"


def test_send_does_not_autodetect_or_fire_control_message(patch_kafka):
    sink = _make_sink()
    sink.send(ndarray([1.0]), ndarray([0]))
    producer = sink._KafkaMLSink__producer
    assert sink.data_type is None  # never auto-detected
    control_sends = [s for s in producer.sent if s["topic"] == "FEDERATED_DATA_CONTROL_TOPIC"]
    assert control_sends == []


def test_send_online_control_msg_computes_format_from_the_sample(patch_kafka):
    sink = _make_sink()
    x = ndarray([1.0])
    y = ndarray([0])
    sink.send_online_control_msg(x, y)

    assert sink.data_type == "float"
    assert sink.label_type == "int"
    producer = sink._KafkaMLSink__producer
    control_sends = [s for s in producer.sent if s["topic"] == "FEDERATED_DATA_CONTROL_TOPIC"]
    assert len(control_sends) == 1
