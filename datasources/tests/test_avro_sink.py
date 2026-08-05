"""Tests for AvroSink - real fastavro encode/decode round trip, not just
mocked calls, since the whole point of this class is the schema-bound
serialization."""

import json

import fastavro
import pytest

from kafkaml_datasources import AvroSink

DATA_SCHEMA = {
    "type": "record",
    "name": "Data",
    "fields": [{"name": "value", "type": "float"}],
}
LABEL_SCHEMA = {
    "type": "record",
    "name": "Label",
    "fields": [{"name": "value", "type": "int"}],
}


@pytest.fixture
def schema_files(tmp_path):
    data_path = tmp_path / "data.avsc"
    label_path = tmp_path / "label.avsc"
    data_path.write_text(json.dumps(DATA_SCHEMA))
    label_path.write_text(json.dumps(LABEL_SCHEMA))
    return str(data_path), str(label_path)


def _make_sink(schema_files, **overrides):
    data_path, label_path = schema_files
    kwargs = dict(
        boostrap_servers="kafka:9092",
        topic="data-topic",
        deployment_id=1,
        data_scheme_filename=data_path,
        label_scheme_filename=label_path,
    )
    kwargs.update(overrides)
    return AvroSink(**kwargs)


def test_input_config_carries_the_raw_schema_text(patch_kafka, schema_files):
    sink = _make_sink(schema_files)
    assert json.loads(sink.input_config["data_scheme"]) == DATA_SCHEMA
    assert json.loads(sink.input_config["label_scheme"]) == LABEL_SCHEMA


def test_send_avro_encodes_and_forwards_bytes_the_schema_can_decode(patch_kafka, schema_files):
    import io

    sink = _make_sink(schema_files)
    sink.send_avro({"value": 3.5}, {"value": 7})

    producer = sink._KafkaMLSink__producer
    sent = producer.sent[-1]
    decoded_data = fastavro.schemaless_reader(io.BytesIO(sent["value"]), sink.avro_data_schema)
    decoded_label = fastavro.schemaless_reader(io.BytesIO(sent["key"]), sink.avro_label_schema)
    assert decoded_data == {"value": pytest.approx(3.5)}
    assert decoded_label == {"value": 7}


def test_send_avro_clears_its_buffers_between_calls(patch_kafka, schema_files):
    """Real bug class this guards against: schemaless_writer appends to an
    io.BytesIO unless it's reset - a forgotten seek(0)/truncate(0) would
    make every message after the first contain all previous ones too."""
    sink = _make_sink(schema_files)
    sink.send_avro({"value": 1.0}, {"value": 1})
    sink.send_avro({"value": 2.0}, {"value": 2})

    producer = sink._KafkaMLSink__producer
    first_len = len(producer.sent[0]["value"])
    second_len = len(producer.sent[1]["value"])
    assert first_len == second_len
