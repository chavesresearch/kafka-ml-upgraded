# Model training

This module contains the training task that will be executed when a TensorFlow training Job is launched in Kafka-ML through Kubernetes. Once deployed, this task waits until a received control message contains the `deployment_id` configured. Once received the control message and the corresponding data stream, the downloaded TensorFlow model from the Back-end will be trained, and the trained model and training and optionally validation results will be sent again to the Back-end.

A brief introduction of its files:
- File `training.py` main file of this module that will be executed when executed the training Job.
- File `mainTraining.py` base class shared by all 9 training modes (single/distributed × classic/incremental, plus federated/blockchain variants) - Kafka data loading, splitting, training loops, metrics reporting.
- File `kafka_dataset.py` `kafka-python`-based Kafka data loading (bounded offset-range replay and streaming/incremental polling) - replaces `tensorflow-io`, see "Behavioral notes" below.
- File `decoders.py` decoders (RAW, Avro, JSON, TELEGRAF_STR_JSON) used to decode data streams.
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

Distributed modes (CASE 3, 4, 7, 8) additionally receive **OPTIMIZER**, **LEARNING_RATE**, **LOSS**, **METRICS** (and `RESULT_URL`/`RESULT_ID` become Python-list-literal strings, one entry per submodel in the chain). Incremental modes (CASE 2, 4, 6, 8) additionally receive **STREAM_TIMEOUT**, **MONITORING_METRIC**, **CHANGE**, **IMPROVEMENT**. Federated modes (CASE 5-8) additionally receive **MODEL_LOGGER_TOPIC**, **FEDERATED_STRING_ID**, **AGGREGATION_ROUNDS**, **DATA_RESTRICTION**, **MIN_DATA**, **AGG_STRATEGY**. Blockchain mode (CASE 9) additionally receives **ETH_RPC_URL**, **ETH_TOKEN_ADDRESS**, **ETH_TOKEN_ABI**, **ETH_CHAIN_ID**, **ETH_NETWORK_ID**, **ETH_WALLET_ADDRESS**, **ETH_WALLET_KEY**, **ETH_BLOCKSCOUT_URL**.

## Behavioral notes vs. the original

- `tensorflow-io` (used for both `KafkaDataset` and `KafkaBatchIODataset`) hasn't shipped a release since mid-2023 and caps out at TF 2.16, so it can't be used with the TensorFlow version this trainer now runs. `kafka_dataset.py` replaces both with `kafka-python`-based equivalents (`get_bounded_kafka_dataset` for classic/distributed replay, `get_streaming_kafka_batches` for incremental/online polling) - same wire format, same offset-range spec, no behavior change from the training code's point of view.
- `decoders.py`'s `AvroDecoder` switched from `tensorflow-io`'s Avro op to `fastavro`, wrapped in `tf.py_function` (fastavro isn't a native TF op, so it can't be traced directly inside a `.map()` call).
- Keras 3 (bundled with modern TensorFlow) removed `Model._get_compile_args()`, requires per-output `metrics=` for multi-output (distributed) models, and re-binds a freshly-loaded model's optimizer to stale pre-save variables unless it's explicitly recompiled via `get_compile_config()`/`compile_from_config()` after `load_model()`. All handled internally - no behavior change from a deployment's point of view.
- Distributed training (`create_distributed_model`, `train_classic_model`, `train_incremental_model`, `test_model`) now explicitly replicates the training label across each submodel's output when compiling/fitting/evaluating a multi-output distributed model - Keras 2 used to silently broadcast a single label across every output, Keras 3 requires the structure to match explicitly. No behavior change, just makes explicit what Keras 2 used to do implicitly.

See `CLAUDE.md` in this directory for the full verification record (which of the 9 training modes were tested end-to-end vs. import/compile-level only, and why).
