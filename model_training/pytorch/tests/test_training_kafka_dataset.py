"""Unit tests for TrainingKafkaDataset's pure helper methods, without
constructing a real dataset (its __init__ does real Kafka I/O immediately -
see CLAUDE.md's "Test infrastructure" for how that's verified end-to-end
instead). Uses __new__ to get a bare instance and calls the (unmangled -
these all end in `__`, so Python's name-mangling doesn't apply) helper
methods directly.

Only the RAW input_format path is covered - AVRO is already flagged in
CLAUDE.md as pre-existing/unreachable/broken (DatumReader is called with a
raw string instead of a parsed schema) and explicitly out of scope to fix
or newly cover here.
"""

from types import SimpleNamespace

import numpy as np

from TrainingKafkaDataset import TrainingKafkaDataset


def _bare_dataset() -> TrainingKafkaDataset:
    return TrainingKafkaDataset.__new__(TrainingKafkaDataset)


def test_split_partitions_into_control_msgs():
    ds = _bare_dataset()
    control_msg = {"topic": "t:0:0:10,t:1:0:5", "input_format": "RAW"}

    result = ds.__splitPartitionsIntoControlMsgs__(control_msg)

    assert [m["topic"] for m in result] == ["t:0:0:10", "t:1:0:5"]
    # original dict untouched, each result entry is its own copy
    assert control_msg["topic"] == "t:0:0:10,t:1:0:5"


def test_split_partitions_single_topic():
    ds = _bare_dataset()
    control_msg = {"topic": "only-topic:0:0:1", "input_format": "RAW"}

    result = ds.__splitPartitionsIntoControlMsgs__(control_msg)

    assert len(result) == 1
    assert result[0]["topic"] == "only-topic:0:0:1"


def test_decodedata_raw_with_reshape():
    ds = _bare_dataset()
    control_message = {
        "input_format": "RAW",
        "input_config": {
            "data_type": "float32",
            "data_reshape": "2 2",
            "label_type": "int32",
            "label_reshape": None,
        },
    }
    record = SimpleNamespace(
        value=np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32).tobytes(),
        key=np.array([5, 6], dtype=np.int32).tobytes(),
    )

    value, label = ds.__decodedata__(record, control_message)

    assert value.shape == (2, 2)
    np.testing.assert_allclose(value, [[1.0, 2.0], [3.0, 4.0]])
    np.testing.assert_array_equal(label, [5, 6])


def test_decodedata_raw_scalar_label_unwrapped():
    """A single-value label is unwrapped to a bare scalar (`len(label) ==
    1` branch), not left as a length-1 array."""
    ds = _bare_dataset()
    control_message = {
        "input_format": "RAW",
        "input_config": {
            "data_type": "float32",
            "data_reshape": None,
            "label_type": "int32",
            "label_reshape": None,
        },
    }
    record = SimpleNamespace(
        value=np.array([1.0, 2.0], dtype=np.float32).tobytes(),
        key=np.array([7], dtype=np.int32).tobytes(),
    )

    value, label = ds.__decodedata__(record, control_message)

    np.testing.assert_allclose(value, [1.0, 2.0])
    assert label == 7
