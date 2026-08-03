import io
import json

import fastavro
from kafka import KafkaProducer


class AvroInference():
    """Class representing a sink of Avro inference data to Apache Kafka.

        Args:
            boostrap_servers (str): List of Kafka brokers
            topic (str): Kafka topic
            data_scheme_filename (str): Filename of the AVRO scheme for training data
            group_id (str): Group ID of the Kafka consumer. Defaults to sink

    """

    def __init__(self, boostrap_servers, topic,
        data_scheme_filename, group_id='sink'):

        self.boostrap_servers= boostrap_servers
        self.topic = topic

        self.data_scheme_filename = data_scheme_filename
        with open(self.data_scheme_filename, "r") as f:
            self.data_schema = f.read()
        self.avro_data_schema = fastavro.parse_schema(json.loads(self.data_schema))

        self.data_io = io.BytesIO()
        self.__producer = KafkaProducer(
            bootstrap_servers=self.boostrap_servers
        )

    def send(self, data):

        fastavro.schemaless_writer(self.data_io, self.avro_data_schema, data)
        data_bytes = self.data_io.getvalue()

        self.__producer.send(self.topic, data_bytes)

        self.data_io.seek(0)
        self.data_io.truncate(0)
        """Cleans data buffer"""

    def close(self):
        self.__producer.flush()
        self.__producer.close()
