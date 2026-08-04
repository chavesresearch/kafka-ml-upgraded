"""Unit tests for the pure decode/type-conversion logic in decoders.py and
utils.py - the parts of this trainer that don't need a live Kafka broker or
a real Kubernetes cluster to exercise. The 9 CASE training modes themselves
are verified separately via real end-to-end runs against a live cluster
(see CLAUDE.md's "Verification done" section) - not practical to reproduce
in CI, so out of scope here.
"""

import fastavro
import numpy as np
import pytest
import tensorflow as tf

from decoders import DecoderFactory, RawDecoder, JsonDecoder, TelegrafStringJsonDecoder, AvroDecoder, _avro_field_tf_dtype
from utils import string_to_numpy_type


# --- string_to_numpy_type ------------------------------------------------

@pytest.mark.parametrize(
    "name,expected",
    [
        ("float", np.float64),
        ("float32", np.float32),
        ("double", np.double),
        ("int64", np.int64),
        ("int32", np.int32),
        ("int16", np.int16),
        ("int8", np.int8),
        ("uint16", np.uint16),
        ("uint8", np.uint8),
        ("string", np.bytes_),
        ("bool", np.bool_),
        ("half", np.half),
    ],
)
def test_string_to_numpy_type_known(name, expected):
    assert string_to_numpy_type(name) is expected


def test_string_to_numpy_type_unknown_raises():
    with pytest.raises(Exception, match="Unsupported type"):
        string_to_numpy_type("not_a_real_type")


# --- _avro_field_tf_dtype --------------------------------------------------

@pytest.mark.parametrize(
    "field_type,expected",
    [
        ("string", tf.string),
        ("bytes", tf.string),
        ("int", tf.int32),
        ("long", tf.int64),
        ("float", tf.float32),
        ("double", tf.float64),
        ("boolean", tf.bool),
        ("some_unknown_type", tf.string),
    ],
)
def test_avro_field_tf_dtype_primitives(field_type, expected):
    assert _avro_field_tf_dtype(field_type) == expected


def test_avro_field_tf_dtype_nullable_union_uses_non_null_branch():
    assert _avro_field_tf_dtype(["null", "int"]) == tf.int32


def test_avro_field_tf_dtype_all_null_union_falls_back_to_string():
    assert _avro_field_tf_dtype(["null"]) == tf.string


# --- DecoderFactory ---------------------------------------------------------

def test_decoder_factory_dispatch():
    assert isinstance(
        DecoderFactory.get_decoder(
            "RAW", {"data_type": "float32", "data_reshape": None, "label_type": "float32", "label_reshape": None}
        ),
        RawDecoder,
    )
    assert isinstance(DecoderFactory.get_decoder("JSON", None), JsonDecoder)


def test_decoder_factory_unknown_format_raises():
    with pytest.raises(ValueError):
        DecoderFactory.get_decoder("NOT_A_FORMAT", None)


# --- RawDecoder --------------------------------------------------------------

def test_raw_decoder_decodes_and_reshapes():
    # A reshape must always be given, even for a scalar (e.g. "1") -
    # RawDecoder passes `label_reshape` straight through to
    # `tf.reshape(res, output_reshape)`, which raises on a bare `None`
    # rather than treating it as "no reshape". Pre-existing behavior
    # (this trainer's real deployments always populate reshape), not
    # something to "fix" here per this module's faithful-port scope.
    decoder = RawDecoder(
        {
            "data_type": "float32",
            "data_reshape": "2 2",
            "label_type": "int32",
            "label_reshape": "1",
        }
    )
    x_bytes = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32).tobytes()
    y_bytes = np.array([7], dtype=np.int32).tobytes()

    x, y = decoder.decode(x_bytes, y_bytes)

    assert x.shape.as_list() == [2, 2]
    np.testing.assert_allclose(x.numpy(), [[1.0, 2.0], [3.0, 4.0]])
    assert y.numpy()[0] == 7


# --- JsonDecoder / TelegrafStringJsonDecoder ---------------------------------

def test_json_decoder():
    assert JsonDecoder().decode('{"a": 1}') == {"a": 1}


def test_telegraf_string_json_decoder():
    payload = '{"fields": {"value": "{\\"a\\": 1}"}}'
    assert TelegrafStringJsonDecoder().decode(payload) == {"a": 1}


# --- AvroDecoder (real fastavro round-trip, no Kafka needed) ----------------

def test_avro_decoder_round_trip():
    schema = fastavro.parse_schema(
        {
            "type": "record",
            "name": "Sample",
            "fields": [{"name": "value", "type": "float"}],
        }
    )
    configuration = {
        "data_scheme": str({"type": "record", "name": "Sample", "fields": [{"name": "value", "type": "float"}]}),
        "label_scheme": str({"type": "record", "name": "Label", "fields": [{"name": "value", "type": "int"}]}),
    }
    decoder = AvroDecoder(configuration)

    import io

    data_buf = io.BytesIO()
    fastavro.schemaless_writer(data_buf, decoder.data_schema, {"value": 3.5})
    label_buf = io.BytesIO()
    fastavro.schemaless_writer(label_buf, decoder.label_schema, {"value": 9})

    res_x, res_y = decoder.decode(
        tf.constant(data_buf.getvalue()), tf.constant(label_buf.getvalue())
    )
    assert pytest.approx(res_x[0].numpy(), abs=1e-5) == 3.5
    assert res_y[0].numpy() == 9
