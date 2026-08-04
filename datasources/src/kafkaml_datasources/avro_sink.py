import io
import json

import fastavro

from .sink import KafkaMLSink


class AvroSink(KafkaMLSink):
    """Class representing a sink of Avro training data to Apache Kafka.

        Args:
            boostrap_servers (str): List of Kafka brokers
            topic (str): Kafka topic
            deployment_id (str): Deployment ID for sending the training
            data_scheme_filename (str): Filename of the AVRO scheme for training data
            label_scheme_filename (str): Filename of the AVRO scheme for label data
            validation_rate (float): rate of the training data for evaluation. Defaults 0
            test_rate (float): rate of the training data for test. Defaults 0
            control_topic (str): Control Kafka topic for sending confirmation after sending training data.
                Defaults to KAFKA_ML_CONTROL_TOPIC
            group_id (str): Group ID of the Kafka consumer. Defaults to sink

    """

    def __init__(self, boostrap_servers, topic, deployment_id,
        data_scheme_filename, label_scheme_filename, description='', validation_rate=0, test_rate=0, control_topic='KAFKA_ML_CONTROL_TOPIC', group_id='sink'):

        input_format='AVRO'
        super().__init__(boostrap_servers, topic, deployment_id, input_format, description, {}, # {} = no data_restrictions
            validation_rate, test_rate, control_topic, group_id)

        self.data_scheme_filename = data_scheme_filename
        with open(self.data_scheme_filename, "r") as f:
            self.data_schema = f.read()
        self.avro_data_schema = fastavro.parse_schema(json.loads(self.data_schema))

        self.label_scheme_filename = label_scheme_filename
        with open(self.label_scheme_filename, "r") as f:
            self.label_schema = f.read()
        self.avro_label_schema = fastavro.parse_schema(json.loads(self.label_schema))

        self.data_io = io.BytesIO()
        self.label_io = io.BytesIO()

        self.input_config =  {
            'data_scheme' : self.data_schema,
            'label_scheme': self.label_schema,
        }

    def send_avro(self, data, label):
        fastavro.schemaless_writer(self.data_io, self.avro_data_schema, data)
        data_bytes = self.data_io.getvalue()

        fastavro.schemaless_writer(self.label_io, self.avro_label_schema, label)
        label_bytes = self.label_io.getvalue()

        self.send(data_bytes, label_bytes)
        """Sends the avro data"""

        self.data_io.seek(0)
        self.data_io.truncate(0)
        """Cleans data buffer"""

        self.label_io.seek(0)
        self.label_io.truncate(0)
        """Cleans label buffer"""
