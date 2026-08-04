"""Unit tests for the pure decode/type-conversion logic in decoders.py and
utils.py - no live Kafka broker or model needed. Mirrors
../../../model_training/tensorflow/tests/test_decoders_and_utils.py's
structure (this service shares the same decoder shapes, minus the
tf.py_function bridging - inference decodes plain numpy, not traced
tf.data pipelines).
"""

import io

import fastavro
import numpy as np
import pytest

from decoders import DecoderFactory, RawDecoder, AvroDecoder, JsonDecoder, TelegrafStringJsonDecoder
from utils import string_to_numpy_type, decode_raw


# --- string_to_numpy_type ------------------------------------------------

@pytest.mark.parametrize(
    "name,expected",
    [
        ("float", np.float64),
        ("float32", np.float32),
        ("int32", np.int32),
        ("uint8", np.uint8),
        ("string", np.bytes_),
        ("bool", np.bool_),
    ],
)
def test_string_to_numpy_type_known(name, expected):
    assert string_to_numpy_type(name) is expected


def test_string_to_numpy_type_unknown_raises():
    with pytest.raises(Exception, match="Unsupported type"):
        string_to_numpy_type("not_a_real_type")


# --- decode_raw / RawDecoder ------------------------------------------------

def test_decode_raw_prepends_batch_dimension():
    # decode_raw always np.insert(reshape, 0, 1, axis=0) - a real message
    # decodes as a batch of 1, matching what a Keras model.predict() call
    # expects.
    x_bytes = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32).tobytes()
    result = decode_raw(x_bytes, np.float32, np.array([2, 2]))
    assert result.shape == (1, 2, 2)
    np.testing.assert_allclose(result, [[[1.0, 2.0], [3.0, 4.0]]])


def test_raw_decoder_decode():
    decoder = RawDecoder({"data_type": "int32", "data_reshape": "2"})
    msg = np.array([10, 20], dtype=np.int32).tobytes()
    result = decoder.decode(msg)
    assert result.shape == (1, 2)
    np.testing.assert_array_equal(result, [[10, 20]])


# --- DecoderFactory ----------------------------------------------------------

def test_decoder_factory_dispatch():
    assert isinstance(
        DecoderFactory.get_decoder("RAW", {"data_type": "float32", "data_reshape": None}), RawDecoder
    )
    assert isinstance(DecoderFactory.get_decoder("JSON", None), JsonDecoder)
    assert isinstance(DecoderFactory.get_decoder("TELEGRAF_STR_JSON", None), TelegrafStringJsonDecoder)


def test_decoder_factory_unknown_format_raises():
    with pytest.raises(ValueError):
        DecoderFactory.get_decoder("NOT_A_FORMAT", None)


# --- JsonDecoder / TelegrafStringJsonDecoder ---------------------------------

def test_json_decoder():
    assert JsonDecoder().decode('{"a": 1}') == {"a": 1}


def test_telegraf_string_json_decoder():
    payload = '{"fields": {"value": "{\\"a\\": 1}"}}'
    assert TelegrafStringJsonDecoder().decode(payload) == {"a": 1}


# --- AvroDecoder (real fastavro round-trip) ----------------------------------

def test_avro_decoder_round_trip():
    schema_dict = {
        "type": "record",
        "name": "Sample",
        "fields": [{"name": "value", "type": "float"}],
    }
    decoder = AvroDecoder({"data_scheme": str(schema_dict)})

    buf = io.BytesIO()
    fastavro.schemaless_writer(buf, decoder.data_schema, {"value": 2.5})

    result = decoder.decode(buf.getvalue())
    assert result == pytest.approx([2.5], abs=1e-5)
