# Model inference

This module contains the inference task that will be executed when a inference Job for a PyTorch ML model is launched in Kafka-ML through Kubernetes. Once deployed, this task waits for data in the input topic configured and send the predictions to the output topic configured.

A brief introduction of its files:
- File `inference.py` main file of this module that will be executed when executed the inference Job.
- File `config.py` to configure debug.
- File `utils.py` common functions used by other files.

## Installation for local development

Dependencies are managed with [uv](https://docs.astral.sh/uv/) - `pyproject.toml` + `uv.lock`, no `requirements.txt`.

```
uv sync
```

Once installed, you have to set each one of the environment vars below to execute the inference task. For instance, you can run `export INPUT_TOPIC=ertis-input` to export the `INPUT_TOPIC` var with the value `ertis-input`. Once configured all the vars, execute `uv run inference.py` to execute the inference task.

See `CLAUDE.md` one level up for the full verification record and behavioral notes.

## Environments vars received

- **BOOTSTRAP_SERVERS**: list of brokers for the connection to Apache Kafka
- **MODEL_ARCH_URL**: URL for downloading the model architecture from the Back-end.
- **MODEL_URL**: URL for downloading the model's trained weights from the Back-end.
- **INPUT_FORMAT**: input format used for decoding.
- **INPUT_CONFIG**: input format configuration used for decoding.
- **INPUT_TOPIC**: Kafka input topic to received data streams.
- **OUTPUT_TOPIC**: Kafka output topic to send the predictions.
- **GROUP_ID**: Kafka group name used mainly when having different container replicas.
