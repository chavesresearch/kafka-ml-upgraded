# TensorFlow Executor (Litestar)

This is a port of `../../mlcode_executor/tfexecutor` from [Flask](https://flask.palletsprojects.com/) to [Litestar](https://litestar.dev/), the same stack `../../backend-litestar` uses, plus a dependency refresh: TensorFlow 2.7.0 → **2.21.0** (and everything else pinned in `requirements.txt` bumped to current stable releases).

The HTTP contract (`POST /exec_tf/`, `/check_deploy_config/`, `/convert_to_tflite/` - request/response shapes, status codes) is unchanged, so it's a drop-in replacement for the Flask service - no changes needed in whichever backend (`../../backend` or `../../backend-litestar`) is deployed, beyond pointing `TFEXECUTOR_URL` at this service.

## Why this needed more than a framework swap

Bumping TensorFlow to latest broke `tensorflow-io`, which the Flask version depended on for two things: streaming Kafka directly into a `tf.data.Dataset` (`tensorflow_io.kafka.KafkaDataset`, used only for int8-quantization calibration data) and Avro decoding (`tfio.experimental.serialization.decode_avro`). `tensorflow-io` hasn't shipped a release since mid-2023 and tops out at TF 2.16, with no maintained fork - so keeping it would have meant keeping TensorFlow 2.5 years out of date indefinitely. Both were replaced:

- **Kafka ingestion**: `app.py`'s `retrieve_representative_dataset` now uses a plain `kafka-python` consumer (revived/actively maintained again - `kafka-python==3.0.9`, contrary to its reputation a couple of years ago) to pull real messages from the deployment's data topic, decoding each one and feeding it straight into the generator the `TFLiteConverter` calls - functionally the same sampling behavior as the old `KafkaDataset`-backed pipeline, just eager Python instead of a lazy graph op.
- **Avro decoding**: `decoders.py`'s `AvroDecoder` now uses `fastavro` (actively maintained, pure-Python) instead of the tensorflow-io op. Schemas are parsed once at decoder construction instead of per-message.

## Installation for local development

Dependencies are managed with [uv](https://docs.astral.sh/uv/) - `pyproject.toml` + `uv.lock`, no `requirements.txt`.

```
uv sync
```

## Running server

```
uv run uvicorn app:app --host 0.0.0.0 --port 8001
```

You can change the IP and port when running the back-end. Note that if you change the IP or port in development mode, you should also change `TFEXECUTOR_URL` in whichever backend is deployed.

## Behavioral notes vs. the Flask version

- `convert_to_tflite` no longer round-trips the converted model through a `.tflite` file on disk before responding - `TFLiteConverter.convert()` already returns the flatbuffer bytes directly. Same output, one less temp-file dance.
- `decoders.py`'s numpy type table drops the removed `np.float`/`np.string`/`np.bool` aliases (gone since NumPy 1.24) in favor of their real names (`np.float64`, `np.bytes_`, `np.bool_`) - same resolved types, just spelled correctly for current NumPy.
- Route handlers are plain `def` (not `async def`) with `sync_to_thread=True`, except `convert_to_tflite` which is `async def` and offloads the blocking conversion via `anyio.to_thread.run_sync` - see the accompanying `CLAUDE.md` for why this isn't just an implementation detail to skip.
