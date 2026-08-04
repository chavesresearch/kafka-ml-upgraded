"""Unit tests for the pure decode logic in decoders.py/utils.py.

Only RAW-format tests here - AVRO is documented dead code in this file
(CLAUDE.md: `AvroDecoder.decode(self, x, y)` takes 2 args but `inference.py`
calls it with 1 - pre-existing, byte-identical to the original, flagged
not fixed). `RawDecoder` also never actually calls `string_to_numpy_type`
(also documented as dead code in CLAUDE.md) - it hands `data_type`
straight to `np.frombuffer`, which parses standard dtype name strings
(`float32`, `int32`, ...) itself. Tests below stick to those standard
names, which is what real Kafka-ML configs use for this service.
"""

import numpy as np
import pytest

from decoders import DecoderFactory, RawDecoder, JsonDecoder, TelegrafStringJsonDecoder
from utils import decode_raw, string_to_numpy_type


def test_string_to_numpy_type_known():
    assert string_to_numpy_type("float32") is np.float32


def test_string_to_numpy_type_unknown_raises():
    with pytest.raises(Exception, match="Unsupported type"):
        string_to_numpy_type("not_a_real_type")


def test_decode_raw_prepends_batch_dimension():
    x_bytes = np.array([1, 2, 3, 4], dtype=np.int32).tobytes()
    result = decode_raw(x_bytes, "int32", np.array([2, 2]))
    assert result.shape == (1, 2, 2)
    np.testing.assert_array_equal(result, [[[1, 2], [3, 4]]])


def test_raw_decoder_decode():
    decoder = RawDecoder({"data_type": "float32", "data_reshape": "2"})
    msg = np.array([1.5, 2.5], dtype=np.float32).tobytes()
    result = decoder.decode(msg)
    assert result.shape == (1, 2)
    np.testing.assert_allclose(result, [[1.5, 2.5]])


def test_raw_decoder_no_reshape():
    decoder = RawDecoder({"data_type": "uint8", "data_reshape": None})
    assert decoder.reshape is None


def test_decoder_factory_dispatch():
    assert isinstance(
        DecoderFactory.get_decoder("RAW", {"data_type": "float32", "data_reshape": None}), RawDecoder
    )
    assert isinstance(DecoderFactory.get_decoder("JSON", None), JsonDecoder)


def test_decoder_factory_unknown_format_raises():
    with pytest.raises(ValueError):
        DecoderFactory.get_decoder("NOT_A_FORMAT", None)


def test_json_decoder():
    assert JsonDecoder().decode('{"a": 1}') == {"a": 1}


def test_telegraf_string_json_decoder():
    payload = '{"fields": {"value": "{\\"a\\": 1}"}}'
    assert TelegrafStringJsonDecoder().decode(payload) == {"a": 1}
