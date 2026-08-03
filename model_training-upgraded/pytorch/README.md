# Model training

This module contains the training task that will be executed when a PyTorch training Job is launched in Kafka-ML through Kubernetes. Once deployed, this task waits until a received control message contains the `deployment_id` configured. Once received the control message and the corresponding data stream, the downloaded PyTorch model from the Back-end will be trained, and the trained model and training and optionally validation results will be sent again to the Back-end.

A brief introduction of its files:
- File `training.py` main file of this module that will be executed when executed the training Job.
- File `TrainingKafkaDataset.py` a `torch.utils.data.Dataset` that reads a bounded Kafka offset range into memory.
- File `config.py` to configure debug.
- File `utils.py` common functions used by other files.

## Installation for local development

Dependencies are managed with [uv](https://docs.astral.sh/uv/) - `pyproject.toml` + `uv.lock`, no `requirements.txt`.

```
uv sync
```

Once installed, you have to set each one of the environment vars below to execute the training task. For instance, you can run `export BOOTSTRAP_SERVERS=localhost:9094` to export the `BOOTSTRAP_SERVERS` var with the value `localhost:9094`. Once configured all the vars, execute `uv run training.py` to execute the training task.

## Environments vars received

- **BOOTSTRAP_SERVERS**: list of brokers for the connection to Apache Kafka
- **RESULT_URL**: URL for downloading the untrained model from the Back-end (GET request). This URL is the same for updating the training results (POST request).
- **RESULT_ID**: Result ID of the model
- **CONTROL_TOPIC**: name of the Kafka control topic used in Kafka-ML
- **DEPLOYMENT_ID**: deployment ID of the configuration to match with the control messages received
- **BATCH**: Batch size used for training and configured in the Front-end
- **KWARGS_FIT**: JSON with the arguments used for training and configured in the Front-end
- **KWARGS_VAL**: JSON with the arguments used for validation and configured in the Front-end
- **CONF_MAT_CONFIG**: whether to generate and upload a confusion matrix image after testing

Unlike the TensorFlow trainer, there is no `CASE` env var here - this module only ever runs a single training mode (non-distributed, non-incremental, non-federated classic training).

## Behavioral notes vs. the original

- `avro`/`ignite`/`numpy` were all bumped to current stable releases with no code changes needed - checked directly against the actual APIs used (see `CLAUDE.md` in this directory for exactly what was verified and how).
- `TrainingKafkaDataset.py`'s `__createconsumer__` now uses `consumer.assign([tp])` instead of relying on a single `consumer.poll()` call to complete the Kafka consumer-group rebalance before `seek()` - the old pattern could raise `ValueError: Unassigned partition` under real Kafka broker latency. Matches the same fix already present elsewhere in this project's `KafkaModelEngine.__createconsumer__`.

See `CLAUDE.md` in this directory for the full verification record, the PyTorch model-code contract (what a submitted model's `code` must define), and what's explicitly out of scope (AVRO input format, confusion matrix generation, GPU path).
