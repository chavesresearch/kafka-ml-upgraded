import torch
from torch import nn
from ignite.metrics import *
import os
import urllib
import time
import logging
import requests
import json
import numpy as np
import torchvision.models as models

from torch.utils import data
from config import *

def download_model(model_url, retries, sleep_time):
  """Downloads the model from the URL received and saves it in the filesystem
  Args:
      model_url(str): URL of the model 
  """
  finished = False
  retry = 0
  while not finished and retry < retries:
    try:
      
      datatowrite = requests.get(model_url, timeout=30).content.decode("utf-8")

      datatowrite = datatowrite.replace("pretrained=True", "pretrained=False")
            
      print(datatowrite)
      exec(datatowrite, None, globals())

      if DEBUG:
        print(model)

      finished = True
      logging.info("Downloaded file model from server!")

      return model
    except Exception as e:
      retry +=1
      logging.error("Error getting the model from backend [%s]", str(e))
      time.sleep(sleep_time)

def download_weights(weights_url, filename, retries, sleep_time):
  """Downloads the model from the URL received and saves it in the filesystem
  Args:
      model_url(str): URL of the model 
  """
  finished = False
  retry = 0
  while not finished and retry < retries:
    try:
      filedata = urllib.request.urlopen(weights_url)
      datatowrite = filedata.read()
      with open(filename, 'wb') as f:
          f.write(datatowrite)
      finished = True
      logging.info("Downloaded model weights from server!")
    except Exception as e:
      retry +=1
      logging.error("Error downloading the model weights [%s]", str(e))
      time.sleep(sleep_time)

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
        raise Exception('string_to_numpy_type: Unsupported type')

def decode_raw(x, output_type, output_reshape):
    """Decodes the raw data received from Kafka and reshapes it if needed.

        Args:
        x (raw): input data
        output_type (numpy type): output type of the received data
        reshape (array): reshape the numpy type (optional)
        
        Returns:
        DType: raw data to tensorflow model loaded
    """
    res = np.frombuffer(x, dtype=output_type)
    output_reshape = np.insert(output_reshape, 0, 1, axis=0)
    res = res.reshape(*output_reshape)
    return res