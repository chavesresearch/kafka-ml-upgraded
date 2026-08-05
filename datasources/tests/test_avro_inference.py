"""Tests for AvroInference - a standalone Avro producer for inference
requests (no KafkaMLSink base, no control topic, no offset tracking)."""

import io
import json

import fastavro
import pytest

from kafkaml_datasources import AvroInference

DATA_SCHEMA = {
    "type": "record",
    "name": "InferenceInput",
    "fields": [{"name": "value", "type": "float"}],
}


@pytest.fixture
def schema_file(tmp_path):
    path = tmp_path / "data.avsc"
    path.write_text(json.dumps(DATA_SCHEMA))
    return str(path)


def _make_inference(schema_file, **overrides):
    kwargs = dict(boostrap_servers="kafka:9092", topic="inference-topic", data_scheme_filename=schema_file)
    kwargs.update(overrides)
    return AvroInference(**kwargs)


def test_send_encodes_and_forwards_decodable_bytes(patch_kafka, schema_file):
    inference = _make_inference(schema_file)
    inference.send({"value": 4.5})

    producer = inference._AvroInference__producer
    sent = producer.sent[-1]
    assert sent["topic"] == "inference-topic"
    decoded = fastavro.schemaless_reader(io.BytesIO(sent["value"]), inference.avro_data_schema)
    assert decoded == {"value": pytest.approx(4.5)}


def test_send_clears_its_buffer_between_calls(patch_kafka, schema_file):
    inference = _make_inference(schema_file)
    inference.send({"value": 1.0})
    inference.send({"value": 2.0})

    producer = inference._AvroInference__producer
    assert len(producer.sent[0]["value"]) == len(producer.sent[1]["value"])


def test_close_flushes_and_closes_the_producer(patch_kafka, schema_file):
    inference = _make_inference(schema_file)
    inference.close()
    producer = inference._AvroInference__producer
    assert producer.flushed is True
    assert producer.closed is True
