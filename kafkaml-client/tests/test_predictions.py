"""Tests for kafkaml_client.predictions (predict_one/predict_batch) and
their KafkaMLClient wrappers - against a faked `kafka.KafkaConsumer`/
`KafkaProducer` (see conftest.py's patch_kafka_module fixture), not a
real broker. Neither fake simulates a real inference deployment
end-to-end (there's no model behind them) - `_echo_predictions_on_send`
below stands in for "a real deployment consumed this input and published
a prediction," by making every send to the input topic immediately
produce a matching, test-controlled prediction on the output topic.
"""

import json

import numpy as np
import pytest

from kafkaml_client import KafkaMLClient
from kafkaml_client.predictions import predict_batch, predict_one


def _prediction(values):
    return json.dumps({"values": values}).encode("utf-8")


def _echo_predictions_on_send(monkeypatch, patch_kafka_module, input_topic, output_topic, next_values):
    """Patches the faked producer's `send` so every message sent to
    `input_topic` immediately gets a matching prediction (from
    `next_values`, called once per input message) published to
    `output_topic` - standing in for a real inference deployment's
    consume-and-publish loop, which nothing in this fake simulates on its
    own."""
    FakeProducer = patch_kafka_module["producer"]
    real_send = FakeProducer.send

    def send(self, topic, value=None, key=None):
        real_send(self, topic, value=value, key=key)
        if topic == input_topic:
            real_send(self, output_topic, value=_prediction(next_values()))

    monkeypatch.setattr(FakeProducer, "send", send)


class TestPredictOne:
    def test_sends_the_row_and_returns_the_one_prediction(self, patch_kafka_module, monkeypatch):
        _echo_predictions_on_send(monkeypatch, patch_kafka_module, "in", "out", lambda: [0.1, 0.9])

        row = np.array([1, 2, 3], dtype="float32")
        prediction = predict_one("localhost:9094", "in", "out", row)

        assert prediction == {"values": [0.1, 0.9]}
        producer = patch_kafka_module["producer"].instances[-1]
        sent_to_input = [m for m in producer.sent if m["topic"] == "in"]
        assert len(sent_to_input) == 1
        assert sent_to_input[0]["value"] == row.tobytes()

    def test_reads_from_earliest_not_the_kafka_python_default_latest(self, patch_kafka_module, monkeypatch):
        # This is the specific bug (missing auto_offset_reset) found and
        # fixed across every examples/*_dataset_inference_example.py
        # script - pinned here so this SDK can't regress into it.
        _echo_predictions_on_send(monkeypatch, patch_kafka_module, "in", "out", lambda: [1.0])

        predict_one("localhost:9094", "in", "out", np.array([1]))

        consumer = patch_kafka_module["consumer"].instances[-1]
        assert consumer.kwargs["auto_offset_reset"] == "earliest"

    def test_accepts_pandas_rows(self, patch_kafka_module, monkeypatch):
        import pandas as pd

        _echo_predictions_on_send(monkeypatch, patch_kafka_module, "in", "out", lambda: [1.0])

        prediction = predict_one("localhost:9094", "in", "out", pd.Series([1, 2, 3]))

        assert prediction == {"values": [1.0]}


class TestPredictBatch:
    def test_sends_every_row_and_returns_predictions_in_order(self, patch_kafka_module, monkeypatch):
        counter = iter(range(10))
        _echo_predictions_on_send(monkeypatch, patch_kafka_module, "in", "out", lambda: [float(next(counter))])

        rows = [np.array([1]), np.array([2]), np.array([3])]
        predictions = predict_batch("localhost:9094", "in", "out", rows)

        assert predictions == [{"values": [0.0]}, {"values": [1.0]}, {"values": [2.0]}]

    def test_raises_timeout_error_if_fewer_predictions_arrive_than_rows(self, patch_kafka_module):
        # No prediction ever gets published to "out" here - simulates a
        # deployment that never responds (or responds too slowly).
        rows = [np.array([1]), np.array([2])]

        with pytest.raises(TimeoutError, match="expected 2"):
            predict_batch("localhost:9094", "in", "out", rows, timeout_ms=1)


class TestKafkaMLClientWrappers:
    def test_predict_one_delegates_to_the_module_function(self, client, patch_kafka_module, monkeypatch):
        _echo_predictions_on_send(monkeypatch, patch_kafka_module, "in", "out", lambda: [1.0])

        prediction = client.predict_one("localhost:9094", "in", "out", np.array([1]))

        assert prediction == {"values": [1.0]}

    def test_predict_batch_delegates_to_the_module_function(self, client, patch_kafka_module, monkeypatch):
        _echo_predictions_on_send(monkeypatch, patch_kafka_module, "in", "out", lambda: [1.0])

        predictions = client.predict_batch("localhost:9094", "in", "out", [np.array([1])])

        assert predictions == [{"values": [1.0]}]


def test_missing_datasets_extra_raises_a_friendly_import_error(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "kafka", None)
    monkeypatch.delitem(sys.modules, "kafkaml_client.predictions", raising=False)

    import importlib

    import kafkaml_client.predictions as predictions_mod

    importlib.reload(predictions_mod)
    with pytest.raises(ImportError, match="datasets.*extra"):
        predictions_mod.predict_one("x", "in", "out", np.array([1]))
