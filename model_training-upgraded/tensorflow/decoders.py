import io
import json

import fastavro
import numpy as np
import tensorflow as tf

from utils import decode_input, string_to_numpy_type

_AVRO_PRIMITIVE_TF_DTYPES = {
    'string': tf.string,
    'bytes': tf.string,
    'int': tf.int32,
    'long': tf.int64,
    'float': tf.float32,
    'double': tf.float64,
    'boolean': tf.bool,
}
"""Maps Avro primitive type names to the tf dtype `tf.py_function` should
produce for that field. Doesn't attempt to handle nested records/arrays/maps
or full union semantics beyond "a nullable primitive" - AvroSink
(datasources-package) only ever writes flat records of primitives, so this
matches what's actually produced on the wire."""


def _avro_field_tf_dtype(field_type):
    """Resolves one Avro field's `type` (possibly a ["null", "<type>"] union
    for a nullable field) to a tf dtype."""
    if isinstance(field_type, list):
        non_null = [t for t in field_type if t != 'null']
        field_type = non_null[0] if non_null else 'string'
    return _AVRO_PRIMITIVE_TF_DTYPES.get(field_type, tf.string)


class DecoderFactory:
    """Factory class for the decoders"""

    @staticmethod
    def get_decoder(input_format, configuration):
        if input_format == 'RAW':
            return RawDecoder(configuration)
        elif input_format == 'AVRO':
            return AvroDecoder(configuration)
        elif input_format == 'JSON':
            return JsonDecoder()
        else:
            raise ValueError(input_format)

class RawDecoder:
    """RAW class decoder implementation
    ARGS:
        configuration (dic): configuration properties
    Attributes:
        datatype(tensorflowtype): tensorflow type
        reshape: reshape of the data
        datatype (:obj:DType): output type of the train data
        reshape_x (:obj:array): reshape for training data (optional)
        labeltype (:obj:DType): output type of the label data
        reshape_y (obj:array): reshape for label data (optional)
    """
    def __init__(self, configuration):
        self.datatype = string_to_numpy_type(configuration['data_type'])
        self.x_reshape = configuration['data_reshape']
        if self.x_reshape is not None:
            self.x_reshape = np.array(self.x_reshape.split(), dtype=int)

        self.labeltype = string_to_numpy_type(configuration['label_type'])
        self.y_reshape = configuration['label_reshape']
        if self.y_reshape is not None:
            self.y_reshape = np.array(self.y_reshape.split(), dtype=int)

    def decode(self, x, y):
        return decode_input(x, y, self.datatype, self.x_reshape, self.labeltype, self.y_reshape)

class AvroDecoder:
    """AVRO class decoder implementation.

    Decodes with `fastavro` instead of the (now unmaintained, TF-2.16-ceiling)
    `tensorflow_io.experimental.serialization.decode_avro`. Unlike that op,
    `fastavro.schemaless_reader` isn't a native TF op, so it can't be traced
    directly inside a `tf.data.Dataset.map()` call the way the old decoder
    was - `decode()` wraps it in `tf.py_function` to bridge eager Python
    execution into the graph-mode `.map()` pipeline `mainTraining.py`'s
    `get_train_data`/`get_online_train_data` build. Schemas are parsed once
    up front via `fastavro.parse_schema` rather than per-message.
    ARGS:
        configuration (dic): configuration properties
    Attributes:
        data_schema (dict): parsed Avro schema for the training data
        label_schema (dict): parsed Avro schema for the label data
    """
    def __init__(self, configuration):
        data_scheme = json.loads(str(configuration['data_scheme']).replace("'", '"'))
        label_scheme = json.loads(str(configuration['label_scheme']).replace("'", '"'))
        self.data_schema = fastavro.parse_schema(data_scheme)
        self.label_schema = fastavro.parse_schema(label_scheme)
        self._data_dtypes = [_avro_field_tf_dtype(f['type']) for f in self.data_schema['fields']]
        self._label_dtypes = [_avro_field_tf_dtype(f['type']) for f in self.label_schema['fields']]

    @staticmethod
    def _decode_one(raw_bytes, schema):
        record = fastavro.schemaless_reader(io.BytesIO(raw_bytes.numpy()), schema)
        return [record[field['name']] for field in schema['fields']]

    def decode(self, x, y):
        res_x = tf.py_function(lambda x: self._decode_one(x, self.data_schema), [x], self._data_dtypes)
        res_y = tf.py_function(lambda y: self._decode_one(y, self.label_schema), [y], self._label_dtypes)
        return (res_x, res_y)

class JsonDecoder:
    """JSON class decoder implementation"""

    def decode(self, x):
        return json.loads(x)

class TelegrafStringJsonDecoder:
    """TELEGRAF_STR_JSON class decoder implementation"""

    def decode(self, x):
        return json.loads(json.loads(x)["fields"]["value"])
