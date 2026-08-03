__author__ = 'Cristian Martin Fdez'


import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen

from kafka import KafkaConsumer, OffsetAndMetadata, TopicPartition

RETRIES = 10
'''Number of retries for requests'''

SLEEP_BETWEEN_REQUESTS = 5
'''Number of seconds between failed requests'''

REQUEST_TIMEOUT = 30
'''Timeout (seconds) for each HTTP request to the backend'''

logger = logging.getLogger(__name__)


class BackendUnreachableError(Exception):
    """Raised when the backend is still unreachable after RETRIES attempts.

    Deliberately lets a message's failure propagate all the way out of
    main() and crash the process, instead of silently moving on to the next
    message (see the commit-ordering note in ``__main__`` for why).
    """


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


def send_datasource_to_backend(url, data):
    """Sends the datasource metadata to the backend, retrying on failure.
    Args:
        url (str): backend /datasources/ endpoint
        data (dict): datasource metadata to send
    Raises:
        BackendUnreachableError: if the backend is still unreachable after RETRIES attempts
    """
    retry = 0
    while retry < RETRIES:
        try:
            request = Request(url, json.dumps(data).encode(), headers={'Content-type': 'application/json'})
            with urlopen(request, timeout=REQUEST_TIMEOUT) as resp:
                resp.read()
            logger.info("Datasource sent to backend!!")
            return
        except Exception as e:
            retry += 1
            logger.error("Error sending data to the backend [%s]. Try again in [%d]s (%d/%d).",
                         str(e), SLEEP_BETWEEN_REQUESTS, retry, RETRIES)
            time.sleep(SLEEP_BETWEEN_REQUESTS)

    raise BackendUnreachableError(f"Backend unreachable after {RETRIES} retries. Datasource lost: {data}")


def build_datasource_payload(msg):
    """Parses a control-topic message into the JSON payload the backend's
    POST /datasources/ expects.
    Args:
        msg: Kafka message received from the control topic
    Returns:
        dict: datasource metadata to send to the backend
    """
    deployment_id = int.from_bytes(msg.key, byteorder='big')

    data = json.loads(msg.value)
    """ Data received from Kafka control topic. Data is a JSON with this format:
        dic={
            'topic': ..,
            'input_format': ..,
            'input_config' : ..,
            'validation_rate' : ..,
            'total_msg': ..
            'description': ..,
        }
    """

    data['deployment'] = str(deployment_id)
    data['input_config'] = json.dumps(data['input_config'])
    # datetime.isoformat() - the backend parses this with
    # datetime.fromisoformat(), which is the actual wire contract now
    # (see backend-litestar/CLAUDE.md's bug list). Don't switch to a
    # hand-rolled strftime format without updating both sides: the previous
    # version's "%Y-%m-%dT%H:%M:%S%Z" silently produced no timezone suffix
    # at all, since %Z renders empty for a naive datetime (which
    # datetime.utcfromtimestamp() - now removed - always returns).
    data['time'] = datetime.fromtimestamp(msg.timestamp / 1000.0, tz=timezone.utc).isoformat()

    return data


if __name__ == '__main__':
  logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S')

  try:
    bootstrap_servers, backend, control_topic = load_environment_vars()
    """Loads the environment information"""

    logger.info("Received environment information (bootstrap_servers, backend, control_topic) ([%s], [%s], [%s])",
                bootstrap_servers, backend, control_topic)

    consumer = KafkaConsumer(control_topic, enable_auto_commit=False, bootstrap_servers=bootstrap_servers, group_id='logger')
    """Starts a Kafka consumer to receive the datasource information from the control topic.
    This forwards every message on the topic to the backend, unfiltered - unlike per-deployment
    consumers (mlcode_executor, model_training) that only care about messages matching their own
    deployment id, this component's job is to archive every datasource submission into the
    backend's DB, regardless of which deployment it belongs to."""

    url = 'http://' + backend + '/datasources/'
    logger.info("Created and connected Kafka consumer for control topic")

    for msg in consumer:
        logger.info("Message received in control topic: %s", msg)
        try:
            data = build_datasource_payload(msg)
            logger.info("Sending datasource to backend: [%s]", data)
            send_datasource_to_backend(url, data)

            # Commit only this message's offset, explicitly - not a bare
            # consumer.commit() (which commits the consumer's *current*
            # position). With a bare commit, a message that permanently
            # fails (see except below, which re-raises instead of
            # continuing) would still get silently swept past the moment
            # a *later* message succeeded and committed, since a plain
            # position-based commit can't distinguish "I processed
            # everything up to here" from "an earlier message actually
            # failed". Combined with re-raising BackendUnreachableError
            # instead of continuing the for-loop, this guarantees we never
            # commit past a message that wasn't actually delivered.
            consumer.commit({
                TopicPartition(msg.topic, msg.partition): OffsetAndMetadata(msg.offset + 1, '')
            })
        except BackendUnreachableError:
            raise
        except Exception as e:
            logger.error("Error with the received datasource [%s]. Waiting for new data.", str(e))

  except BackendUnreachableError as e:
    logger.error(str(e))
    logger.error("Component will be restarted.")
    sys.exit(1)
  except Exception as e:
    logger.error("Error in main [%s]. Component will be restarted.", str(e), exc_info=True)
    sys.exit(1)
