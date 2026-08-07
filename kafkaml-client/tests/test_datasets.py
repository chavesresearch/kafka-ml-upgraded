"""Tests for kafkaml_client.datasets (send_dataset/send_dataframe) and
their KafkaMLClient.send_dataset/.send_dataframe wrappers - against a
faked kafkaml_datasources.RawSink's underlying Kafka client (see
conftest.py's patch_kafka fixture), not a real broker. Real numpy arrays
and pandas DataFrames/Series are used throughout (both are real
dependencies of this test suite, via the dev group) - this exercises the
actual duck-typing contract kafkaml_datasources.RawSink expects, not a
stand-in for it.
"""

import json
import sys

import numpy as np
import pandas as pd
import pytest

from kafkaml_client import KafkaMLClient
from kafkaml_client.datasets import send_dataframe, send_dataset


def _control_message(producer):
    """The last message RawSink.close() sends is always the control-topic
    registration message - every other message is a data row."""
    return producer.sent[-1]


class TestSendDataset:
    def test_sends_one_message_per_row_plus_a_control_message(self, patch_kafka):
        data = np.array([[1, 2], [3, 4], [5, 6]], dtype="uint8")
        labels = np.array([0, 1, 0], dtype="uint8")

        send_dataset("localhost:9094", topic="t", deployment_id=7, data=data, labels=labels)

        producer = patch_kafka["producer"].instances[-1]
        # 3 data rows + 1 control message.
        assert len(producer.sent) == 4
        control = _control_message(producer)
        assert control["topic"] == "KAFKA_ML_CONTROL_TOPIC"
        body = json.loads(control["value"])
        assert body["total_msg"] == 3
        assert body["input_format"] == "RAW"

    def test_deployment_id_is_encoded_as_the_control_messages_key(self, patch_kafka):
        data = np.array([[1], [2]], dtype="uint8")
        labels = np.array([0, 1], dtype="uint8")

        send_dataset("localhost:9094", topic="t", deployment_id=300, data=data, labels=labels)

        control = _control_message(patch_kafka["producer"].instances[-1])
        assert int.from_bytes(control["key"], byteorder="big") == 300

    def test_accepts_pandas_series_and_dataframe(self, patch_kafka):
        data = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        labels = pd.Series([0, 1, 0])

        send_dataset("localhost:9094", topic="t", deployment_id=1, data=data, labels=labels)

        producer = patch_kafka["producer"].instances[-1]
        assert len(producer.sent) == 4  # 3 rows + control message
        assert json.loads(_control_message(producer)["value"])["total_msg"] == 3

    def test_mismatched_lengths_raise_before_touching_kafka(self, patch_kafka):
        data = np.array([[1], [2], [3]])
        labels = np.array([0, 1])

        with pytest.raises(ValueError, match="same length"):
            send_dataset("localhost:9094", topic="t", deployment_id=1, data=data, labels=labels)

        # The length check happens before RawSink (and therefore any
        # Kafka client) is even constructed.
        assert patch_kafka["producer"].instances == []
        assert patch_kafka["consumer"].instances == []

    def test_passes_validation_and_test_rate_through(self, patch_kafka):
        data = np.array([[1], [2]])
        labels = np.array([0, 1])

        send_dataset(
            "localhost:9094",
            topic="t",
            deployment_id=1,
            data=data,
            labels=labels,
            validation_rate=0.2,
            test_rate=0.1,
            description="my dataset",
        )

        body = json.loads(_control_message(patch_kafka["producer"].instances[-1])["value"])
        assert body["validation_rate"] == 0.2
        assert body["test_rate"] == 0.1
        assert body["description"] == "my dataset"

    def test_registers_even_if_a_mid_stream_send_raises(self, patch_kafka):
        # Second row isn't a real ndarray, so RawSink.send() blows up on
        # it (no .tobytes()) after the first row already went through -
        # close() (and therefore registration) must still fire so a
        # partial send isn't left unregistered.
        data = [np.array([1], dtype="uint8"), "not an array"]
        labels = np.array([0, 1], dtype="uint8")

        with pytest.raises(AttributeError):
            send_dataset("localhost:9094", topic="t", deployment_id=1, data=data, labels=labels)

        producer = patch_kafka["producer"].instances[-1]
        data_sent = [m for m in producer.sent if m["topic"] == "t"]
        assert len(data_sent) == 1  # only the first row got through before the crash
        assert json.loads(_control_message(producer)["value"])["total_msg"] == 1


class TestSendDataframe:
    def test_splits_label_column_from_the_rest(self, patch_kafka):
        df = pd.DataFrame({"x1": [1, 2, 3], "x2": [4, 5, 6], "y": [0, 1, 0]})

        send_dataframe("localhost:9094", topic="t", deployment_id=1, dataframe=df, label_column="y")

        producer = patch_kafka["producer"].instances[-1]
        assert len(producer.sent) == 4  # 3 rows + control message
        assert json.loads(_control_message(producer)["value"])["total_msg"] == 3


class TestKafkaMLClientWrappers:
    def test_send_dataset_delegates_to_the_module_function(self, client, patch_kafka):
        data = np.array([[1], [2]], dtype="uint8")
        labels = np.array([0, 1], dtype="uint8")

        client.send_dataset("localhost:9094", topic="t", deployment_id=1, data=data, labels=labels)

        producer = patch_kafka["producer"].instances[-1]
        assert len(producer.sent) == 3  # 2 rows + control message

    def test_send_dataframe_delegates_to_the_module_function(self, client, patch_kafka):
        df = pd.DataFrame({"x": [1, 2], "y": [0, 1]})

        client.send_dataframe("localhost:9094", topic="t", deployment_id=1, dataframe=df, label_column="y")

        producer = patch_kafka["producer"].instances[-1]
        assert len(producer.sent) == 3  # 2 rows + control message


def test_missing_datasets_extra_raises_a_friendly_import_error(monkeypatch):
    # Simulates kafkaml-datasources not being installed (the 'datasets'
    # extra not present) - `None` in sys.modules makes Python's import
    # machinery raise ImportError immediately, the same failure mode a
    # real missing package produces.
    monkeypatch.setitem(sys.modules, "kafkaml_datasources", None)
    monkeypatch.delitem(sys.modules, "kafkaml_client.datasets", raising=False)

    import importlib

    import kafkaml_client.datasets as datasets_mod

    importlib.reload(datasets_mod)
    with pytest.raises(ImportError, match="datasets.*extra"):
        datasets_mod.send_dataset("x", "t", 1, [], [])
