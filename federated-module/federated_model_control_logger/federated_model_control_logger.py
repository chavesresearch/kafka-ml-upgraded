__author__ = 'Antonio J. Chaves'


from kafka import KafkaConsumer
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import traceback
import logging
import sys
import os
import json
import time
import datetime
from uuid import uuid4

RETRIES = 10
'''Number of retries for requests'''

SLEEP_BETWEEN_REQUESTS = 5
'''Number of seconds between failed requests'''

def load_environment_vars():
  """Loads the environment information receivedfrom dockers
  boostrap_servers, backend, control_topic
  Returns:
      boostrap_servers (str): list of boostrap server for the Kafka connection
      backend (str): hostname of the backend
      control_topic (str): name of the control topic
  """
  bootstrap_servers = os.environ.get('BOOTSTRAP_SERVERS')
  backend = os.environ.get('BACKEND')
  control_topic = os.environ.get('CONTROL_TOPIC')

  return (bootstrap_servers, backend, control_topic)

if __name__ == '__main__':
  try:
    logging.basicConfig(
          stream=sys.stdout,
          level=logging.INFO,
          format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s: %(message)s',
          datefmt='%Y-%m-%d %H:%M:%S')

    bootstrap_servers, backend, control_topic = load_environment_vars()
    """Loads the environment information"""

    logging.info("Received environment information (bootstrap_servers, backend, control_topic, control_topic) ([%s], [%s], [%s])", 
              bootstrap_servers, backend, control_topic)
    
    # Real bug, found via actually restarting this service and watching
    # what it re-sent (not by inspection): `auto_offset_reset='earliest'`
    # here, combined with a fresh random `group_id` on every restart (no
    # prior committed offset for a brand-new group to resume from), means
    # *every* restart replays this topic's *entire* retained history from
    # the very beginning - every ModelSource registration ever published,
    # re-POSTed to federated_backend at once. Confirmed via
    # `kubectl logs` on a real restart: offsets 3 through 9 (7 old
    # registrations spanning hours) were all replayed and re-sent in the
    # same second. The sibling `federated_data_control_logger.py` doesn't
    # pass this kwarg at all, so it correctly defaults to `'latest'` - a
    # fresh group only sees new messages, exactly the asymmetry that made
    # this hard to spot (one of the two loggers behaved correctly).
    # Combined with federated_backend's own now-fixed "never marks
    # consumed" gap (see federated-module/CLAUDE.md), this is what spawned
    # duplicate edge worker Jobs from hours-old registrations on every
    # restart. Dropped to match the sibling's correct default.
    consumer = KafkaConsumer(control_topic, enable_auto_commit=False, bootstrap_servers=bootstrap_servers, group_id=f'federated_model_control_logger-{uuid4().hex[:8]}')
    """Starts a Kafka consumer to receive the datasource information from the control topic"""
    
    url = 'http://'+backend+'/model-control-logger/' 
    logging.info("Created and connected Kafka consumer for control topic")

    for msg in consumer:
        """Gets a new message from Kafka control topic"""
        logging.info("Message received in control topic")
        logging.info(msg)
        try:            
          data = json.loads(msg.value)
          """ Data received from Kafka control topic. Data is a JSON with this format:
              dic={
                'model_format': {'input_shape': '28 28', 'output_shape': '10'}, 'federated_params': {'federated_string_id': 'DEBUG', 'data_restriction': {} , 'framework': 'tf'}
                }
          """          
          retry = 0
          ok = False

          data['time'] = datetime.datetime.utcfromtimestamp(msg.timestamp/1000.0).strftime("%Y-%m-%dT%H:%M:%S%Z")
          
          logging.info("Sending model datasource to backend: [%s]", data)

          while not ok and retry < RETRIES:
            try:
              request = Request(url, json.dumps(data).encode(), headers={'Content-type': 'application/json'})
              with urlopen(request) as resp:
                res = resp.read()
                ok = True
                resp.close()
              logging.info("Model datasource sent to backend!!")

              consumer.commit()
              """commit the offset to Kafka after sending the data to the backend"""           
            
            except Exception as e:
              retry+=1
              time.sleep(SLEEP_BETWEEN_REQUESTS)
              logging.error("Error sending data to the backend [%s]. Try again in [%d]s.", str(e), SLEEP_BETWEEN_REQUESTS)

        except Exception as e:
          logging.error("Error with the received datasource [%s]. Waiting for new data.", str(e))
  except Exception as e:
          traceback.print_exc()
          logging.error("Error in main [%s]. Component will be restarted.", str(e))