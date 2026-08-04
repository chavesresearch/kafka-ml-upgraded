import io
import json

import fastavro
import numpy as np

from utils import *

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
        elif input_format == 'TELEGRAF_STR_JSON':
            return TelegrafStringJsonDecoder()
        else:
            raise ValueError(input_format)

class RawDecoder:
    """RAW class decoder implementation
        ARGS:
            configuration (dic): configuration properties
        Attributes:
            datatype(numpytype): numpy type
            reshape: reshape of the data

    """
    def __init__(self, configuration):
        self.datatype = string_to_numpy_type(configuration['data_type'])
        self.reshape = configuration['data_reshape']
        if self.reshape is not None:
            self.reshape = np.fromstring(self.reshape, dtype=int, sep=' ')
    
    def decode(self, msg):
        return decode_raw(msg, self.datatype, self.reshape)

class AvroDecoder:
    """AVRO class decoder implementation.

    Decodes with `fastavro` instead of the (now unmaintained,
    TF-2.16-ceiling) `tensorflow_io.experimental.serialization.decode_avro`
    - same replacement already applied in
    `mlcode_executor/tfexecutor/decoders.py` and
    `model_training/tensorflow/decoders.py`. Schema is parsed once
    up front via `fastavro.parse_schema` rather than per-message; decoding
    happens eagerly in plain Python, fine here since `decode()` is called
    synchronously per Kafka message, never inside a traced `tf.data`
    pipeline.
        ARGS:
            configuration (dic): configuration properties
        Attributes:
            data_schema (dict): parsed Avro schema for the input data

    """
    def __init__(self, configuration):
        data_scheme = json.loads(str(configuration['data_scheme']).replace("'", '"'))
        self.data_schema = fastavro.parse_schema(data_scheme)

    def decode(self, msg):
        record = fastavro.schemaless_reader(io.BytesIO(msg), self.data_schema)
        return [record[field['name']] for field in self.data_schema['fields']]

class JsonDecoder:
    """JSON class decoder implementation"""

    def decode(self, x):
        return json.loads(x)
    
class TelegrafStringJsonDecoder:
    """TELEGRAF_STR_JSON class decoder implementation"""
    
    def decode(self, x):
        return json.loads(json.loads(x)["fields"]["value"])