---
sidebar_position: 6
---

# mlcode_executor

`mlcode_executor/` validates model code before `backend` will accept it.
It's two independent HTTP services — `tfexecutor` (TensorFlow) and
`pthexecutor` (PyTorch) — each of which actually `exec()`s the
user-submitted model code in a throwaway subprocess and reports back
whether that succeeded. `backend` calls whichever one matches the
model's declared framework; see the [backend page](./backend)'s "Talking
to `mlcode_executor`" section for the caller side.

## Stack

Both services are [Litestar](https://litestar.dev/) 2.24.0 apps (same
framework `backend` uses) served by `uvicorn[standard]`. `tfexecutor`
additionally depends on `kafka-python` (a synchronous, single-consumer
use — see below) and `fastavro` for Avro decoding. The two services are
pinned to *different* Python versions on purpose: `pthexecutor` runs on
`python:3.12-slim`, while `tfexecutor` is capped at `>=3.11,<3.12`
because the official `tensorflow/tensorflow:2.21.0` base image itself
ships Python 3.11, not 3.12.

## Endpoints

Both services expose the same URL paths and response shapes as the
original Flask-based implementation, so `backend` only needs
`TFEXECUTOR_URL`/`PTHEXECUTOR_URL` pointed at them — no backend-side
contract changes.

| Path | Service | Purpose |
|---|---|---|
| `POST /exec_tf/` | tfexecutor | `exec()`s submitted model code; can also save the model to `.h5` or report its input shape. |
| `POST /exec_pth/` | pthexecutor | Same, for PyTorch/`nn.Module` code. |
| `POST /check_deploy_config/` | both | Sanity-checks a deployment's `fit`/`evaluate` kwargs by running one real epoch against synthetic sample data. |
| `POST /convert_to_tflite/` | tfexecutor only | Converts a trained `.h5` model to TFLite, with optional dynamic or int8 quantization. |

### `exec_tf` / `exec_pth`: the exec() sandbox

`exec_model(imports_code, model_code, distributed)` in each `app.py`
runs, in order: any caller-supplied `imports_code`, then the model code
itself, via plain `exec(code, None, globals())`. This means whatever
names are bound at module scope in `app.py` are implicitly available to
submitted code without it importing them — `tfexecutor/app.py` keeps
`from tensorflow import keras` and `import tensorflow_datasets as tfds`
specifically so a submitted model can reference `keras.Sequential(...)`
unqualified; `pthexecutor/app.py` keeps a wildcard `from ignite.metrics
import *` for the same reason (`Accuracy()`, `Precision()`, etc.). A
`distributed` model's code is reformatted first (`format_ml_code`
appends `model = ` to the code's last line) since a distributed child
model's submitted code is written as a bare expression, not an
assignment.

Both handlers run the actual `exec_model()` call inside a **subprocess**
(`multiprocessing.get_context("spawn")`), not in the request-handling
thread. Two reasons this matters:

- Python has no supported way to forcibly kill a thread stuck in an
  infinite loop, but a subprocess can be `terminate()`d/`kill()`ed — so a
  submission that hangs (deliberately or not) can't pin a worker
  forever. Both handlers enforce a 60-second wall-clock cap
  (`EXEC_TIMEOUT_S`) via `result_queue.get(timeout=...)`, then
  escalate `terminate()` → `kill()` if the process is still alive.
- `spawn` (not `fork`) is required for TensorFlow/CUDA safety — a forked
  child would inherit the parent's already-initialized GPU context,
  which TF/CUDA doesn't support safely across `fork()`.

The result is read off a `multiprocessing.Queue` *before* joining the
child process — reading after `join()` can deadlock if the child's
`put()` is blocked on a payload larger than the OS pipe buffer (e.g. a
real `.h5` file), since the child can't exit until something drains the
queue, and `join()` is waiting for the child to exit first. Only
JSON/bytes-safe values cross the queue (model objects themselves aren't
reliably picklable back across the process boundary) — for a
`load_model` request, the child model-saves to a temp `.h5` file,
reads the bytes back, and puts those bytes on the queue instead of the
model object.

`check_deploy_config` doesn't touch submitted model code at all — it
builds a small synthetic sample model and dataset (`get_sample_model`/
`get_sample_data`) and runs one real epoch of `fit`/`evaluate` (tf) or
one `trainer.run`/evaluator pass (pth, via `ignite`) using the
deployment's actual `kwargs_fit`/`kwargs_val`, just capped to a single
epoch. This is how a bad `batch`/`epochs`/kwarg value gets caught before
a real Kubernetes training Job is ever submitted.

### `convert_to_tflite`: multipart, quantization, and int8 calibration

Unlike the other handlers, `convert_to_tflite` is `async def` (not a
`sync_to_thread` sync handler) because it needs `await request.form()`
to read the multipart body; the actual blocking TFLite conversion work
is offloaded manually with `await anyio.to_thread.run_sync(...)`. The
uploaded file's multipart **field name is the model filename itself**
(e.g. `"42.h5"`), not a fixed field like `"file"` — this matches how
`backend` posts it (`files={f"{result_id}.h5": ...}`), so the handler
scans `form.items()` for an `UploadFile` whose field name ends in
`.h5` rather than looking up a known key.

Quantization has two modes, both driven by `quantization_params`:

- **Dynamic** — just sets `converter.optimizations = [tf.lite.Optimize.DEFAULT]`.
- **int8** — additionally sets `converter.representative_dataset` to a
  generator (`retrieve_representative_dataset`) that samples real data
  from Kafka for calibration. That generator first waits on the Kafka
  *control* topic for the message matching the deployment id (same
  control-topic wire format the [datasources](./datasources) package
  publishes and [kafka_control_logger](./kafka-control-logger) forwards
  to `backend`), then opens a second, plain `kafka-python` consumer on
  the datasource's actual data topic(s) and decodes up to
  `repr_data_size` (default 100) messages with the same `DecoderFactory`
  (`decoders.py`) the RAW/AVRO/JSON formats use. This replaces the
  original Flask version's `tensorflow_io.kafka.KafkaDataset`-based
  pipeline — `tensorflow-io` hasn't shipped a release since mid-2023 and
  caps out at TF 2.16, so both the Kafka-streaming and Avro-decoding
  pieces it used to provide were reimplemented directly on
  `kafka-python` and `fastavro`.

`kafka-python` (not `aiokafka`, which `backend` uses) is a deliberate
choice here: the Kafka consumption in this service is a single bounded,
sequential, blocking operation (wait for one control message, then
stream up to N data messages) driven from a synchronous handler — there
is no concurrency to gain from async in this specific path.

### Decoders

`tfexecutor/decoders.py`'s `DecoderFactory.get_decoder(input_format,
configuration)` returns a `RawDecoder`, `AvroDecoder`, or `JsonDecoder`
matching the datasource's declared `input_format`. `AvroDecoder` parses
its schemas once up front with `fastavro.parse_schema` and decodes with
`fastavro.schemaless_reader` — the direct replacement for
`tfio.experimental.serialization.decode_avro`. Note that
`retrieve_representative_dataset` always calls `decoder.decode(msg.value,
msg.key)` with two arguments regardless of which decoder was returned,
but `JsonDecoder.decode` only accepts one — a pre-existing bug (present
in the original Flask version too) that means int8 quantization over a
JSON-format datasource will raise `TypeError` on the first sampled
message. RAW and AVRO datasources are unaffected.

## Error reporting back to `backend`

None of the endpoints return structured error bodies — a failure is
communicated purely through the HTTP status code:

- `200` — success. For `exec_tf`/`exec_pth`'s `load_model`/`input_shape`
  request types, the body carries the actual payload (model bytes or a
  shape string); otherwise the body is empty.
- `400` — the submitted code raised an exception during `exec()`, a
  deploy-config sanity check failed, or TFLite conversion failed. The
  exception is logged server-side (`logger.error`) but not included in
  the response body.
- `404` — an unrecognized `request_type` was sent to `exec_tf`/`exec_pth`.

`backend` treats a non-`200` response from these calls as "the submitted
code/config is invalid" and rejects the corresponding model create/edit
or deployment.

## See also

- [backend](./backend) — the caller; see its "Talking to
  `mlcode_executor`" and "Why there's no Kafka producer" sections.
- [datasources](./datasources) — publishes the control-topic messages
  `retrieve_representative_dataset` consumes for int8 calibration.
- [kafka-control-logger](./kafka-control-logger) — the other consumer
  of that same control topic.
- [model-training](./model-training) — the training containers that
  consume Kafka data in the same RAW/AVRO/JSON shapes these decoders
  handle.
