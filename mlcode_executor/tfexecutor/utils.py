import tensorflow as tf
import numpy as np

_NUMPY_TYPES = {
    "half": np.half,
    # Bare "float" used to be resolved via the now-removed `np.float` alias,
    # which was itself just an alias for the builtin `float` (i.e. a C
    # double / float64) - NOT float32. Kept distinct from "float32" below to
    # preserve that original precision.
    "float": np.float64,
    "float32": np.float32,
    "double": np.double,
    "int64": np.int64,
    "int32": np.int32,
    "int16": np.int16,
    "int8": np.int8,
    "uint16": np.uint16,
    "uint8": np.uint8,
    # np.string / np.bool were removed aliases for np.bytes_ / np.bool_.
    "string": np.bytes_,
    "bool": np.bool_,
}


def string_to_numpy_type(out_type):
    """Converts a string with the same name to a Numpy type.
    Acceptable types are half, float, double, int32, uint16, uint8,
                int16, int8, int64, string, bool.
    Args:
        out_type (str): Output type to convert
    Returns:
        Numpy DType: Numpy DType of the intput
    """
    try:
        return _NUMPY_TYPES[out_type]
    except KeyError:
        raise Exception("string_to_numpy_type: Unsupported type")


def decode_raw(x, output_type, output_reshape):
    """Decodes the raw data received from Kafka and reshapes it if needed.
    Args:
        x (raw): input data
        output_type (numpy type): output type of the received data
        reshape (array): reshape the numpy type (optional)
    Returns:
        DType: raw data to tensorflow model loaded
    """
    res = tf.io.decode_raw(x, out_type=output_type)
    res = tf.reshape(res, output_reshape)
    return res


def decode_input(x, y, output_type_x, reshape_x, output_type_y, reshape_y):
    """Decodes the input data received from Kafka and reshapes it if needed.
    Args:
        x (bytes): train data
        output_type_x (:obj:DType): output type of the train data
        reshape_x (:obj:`list`): reshape the tensorflow train data (optional)
        y (bytes): label data
        out_type_y (:obj:DType): output type of the label data
        reshape_y (:obj:`list`): reshape the tensorflow label data (optional)
    Returns:
        tuple: tuple with the (train, label) data received
    """
    x = decode_raw(x, output_type_x, reshape_x)
    y = decode_raw(y, output_type_y, reshape_y)
    return (x, y)
