# kafkaml-datasources

This is a reimplementation of `../datasources` (a folder of standalone files meant to be copied into your project) as a proper installable Python package, `kafkaml_datasources`. Same classes, same constructor signatures, same wire format on Kafka - so existing example scripts (`../examples/*/*.py`) work by changing only the import line:

```diff
- from datasources.raw_sink import RawSink
+ from kafkaml_datasources import RawSink
```

## Installation

Dependencies are managed with [uv](https://docs.astral.sh/uv/). To use this in your own project:

```
uv add /path/to/datasources-package
```

or, without uv:

```
pip install /path/to/datasources-package
```

For local development on the package itself:

```
uv sync
```

## Classes

- `KafkaMLSink` - base class used by every sink below.
- `RawSink` - send RAW-format training data.
- `AvroSink` - send Avro-format training data (requires an Avro schema file for data and one for labels).
- `OnlineRawSink` - RAW format for online/incremental training scenarios.
- `FederatedRawSink` / `OnlineFederatedRawSink` - RAW format for federated learning topics.
- `AvroInference` - send Avro-format inference data (not a `KafkaMLSink` subclass - no control topic message, no label).

## What changed vs. `../datasources`

- **Packaged properly**: `src/kafkaml_datasources/` + `pyproject.toml` + `uv.lock`, importable as `kafkaml_datasources` instead of copying loose files into your project's `datasources/` folder.
- **Avro switched from `avro-python3` to `fastavro`**: `avro-python3` hasn't had a release since March 2021 (its functionality was folded back into the official `avro` package years ago). `fastavro` is actively maintained and is what `mlcode_executor-litestar/tfexecutor` already uses for the matching *decode* side, so both ends of the Avro pipeline now use the same library.
- **`kafka-python` bumped `2.0.2` → `3.0.9`** (actively maintained again - verify current status before assuming otherwise if it comes up again).
- **Offset tracking no longer does a manual per-partition round trip.** `KafkaMLSink` used to call `assign()` + `seek_to_end()` + `position()` once per partition (each its own broker round trip) to figure out how many messages were sent between session start and `close()`. Replaced with a single batched `KafkaConsumer.end_offsets(partitions)` call at each of those two points - same information, fewer round trips, and no more mutating the shared consumer's partition assignment on every call for a consumer that's never actually used to read messages.
- **Deployment id in the control-message key widened to 4 bytes.** The original `bytes([deployment_id])` raised `ValueError` for any deployment id ≥ 256. Every consumer of this key (`kafka_control_logger`, `mlcode_executor/tfexecutor`, `model_training/*`) already decodes it generically via `int.from_bytes(msg.key, byteorder="big")`, so this is wire-compatible regardless of key width - verified with a real end-to-end test (deployment id 300, see `CLAUDE.md`).

## Verified with a real broker

Unlike a from-inspection review, this was checked against an actual single-broker Kafka instance (Docker, KRaft mode): `RawSink` with a deployment id of 300 (>255, the old encoding's ceiling) sent data + a control message, `kafka_control_logger` picked it up, and `backend-litestar` persisted exactly one `Datasource` row with no duplication. See `CLAUDE.md` for the full setup and what it caught.
