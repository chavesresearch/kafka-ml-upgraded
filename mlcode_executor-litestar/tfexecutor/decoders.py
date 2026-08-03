import io
import json

import fastavro
import numpy as np

from utils import decode_input, string_to_numpy_type


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

    Decodes with `fastavro` instead of the (now unmaintained,
    TF-2.16-ceiling) `tensorflow_io.experimental.serialization.decode_avro`.
    Schemas are parsed once up front via `fastavro.parse_schema` rather than
    per-message, and decoding happens eagerly in plain Python/numpy instead
    of as a graph op - fine here since `decode()` is only ever called from
    the representative-dataset generator (see `app.py`), never inside a
    `tf.data.Dataset.map()`.
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

    @staticmethod
    def _decode_one(raw_bytes, schema):
        record = fastavro.schemaless_reader(io.BytesIO(raw_bytes), schema)
        return [record[field['name']] for field in schema['fields']]

    def decode(self, x, y):
        return (self._decode_one(x, self.data_schema), self._decode_one(y, self.label_schema))

class JsonDecoder:
    """JSON class decoder implementation"""

    def decode(self, x):
        return json.loads(x)

class TelegrafStringJsonDecoder:
    """TELEGRAF_STR_JSON class decoder implementation"""

    def decode(self, x):
        return json.loads(json.loads(x)["fields"]["value"])
