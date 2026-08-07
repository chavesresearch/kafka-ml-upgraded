# kafkaml-client — instructions for AI assistants

A draft/proof-of-concept Python SDK for the Kafka-ML backend REST API,
built in response to the user's own idea: "being able to interact with
the Kafka-ML backend with a python package instead of with the api or the
frontend, being more user-friendly at code."

## What it wraps

`backend`'s `/models/`, `/configurations/`, `/deployments/`,
`/results/`, `/results/inference/{id}`, `/inferences/{id}` endpoints -
the core CRUD + the "wait until a real training result finishes" polling
loop. Does **not** wrap the entire backend surface yet: datasources, IoT
devices, and the websocket visualization relay aren't covered.

## Where the logic came from

Lifted directly from `integration-tests/common.py`, which needed almost
exactly this (build a model/configuration/deployment payload, POST it,
look the new id back up since these endpoints don't return the created
object, poll `/results/` until a status is reached) for its own tests.
Rather than let that logic live buried in a test helper, it was extracted
here as a real, reusable package - and `integration-tests/common.py` was
then rewritten to *depend on this package* and call through to it
(dogfooding: proves the client actually works for real requests, not just
that it imports).

## Verified with

The full `integration-tests/` suite (all 6 tests: TF CASE 1-4, PyTorch,
inference) was re-run end-to-end after `common.py` was switched over to
delegate to `KafkaMLClient`, against the real live cluster - every real
model/configuration/deployment/inference create, and the real training/
inference results, went through this client's code, not a bypassed path.
See `integration-tests/README.md` for what that suite actually exercises
(and doesn't).

## Automated test suite (2026-08-06)

`tests/` (23 tests, `uv run pytest -v`, CI via `.github/workflows/
kafkaml-client.yml`) - didn't exist before this date, only the
integration-tests dogfooding above. Uses a small in-memory fake backend
wired in via `httpx.MockTransport` (httpx's own supported way to test
client code) - `KafkaMLClient.__init__` builds its own `httpx.Client`
with no injection point, so tests construct a real client normally then
swap its `_http` attribute for one backed by the mock transport
(reaching into a "private" attribute deliberately - this SDK is a
documented draft/PoC, not worth adding DI machinery to yet just for one
fixture). Covers the id-lookup-after-create logic every create method
needs, the before/after id-diffing `create_deployment`/`deploy_inference`
use instead, `KafkaMLError` wrapping, and `wait_for_results`' polling/
timeout/`min_results` behavior - the client's own logic, not the real
backend's behavior (that's `backend/tests`' job). Same Python-3.9-safe
`pytest==8.4.2` pin as `datasources` - see that package's `CLAUDE.md` for
why.

## Numpy/pandas dataset -> datasource support (2026-08-07)

`kafkaml_client.datasets.send_dataset`/`send_dataframe` (also exposed as
`KafkaMLClient.send_dataset`/`.send_dataframe`) send a numpy/pandas
dataset to Kafka and register it as a datasource for a deployment - the
same flow every `examples/*/*_dataset_training_example.py` script
hand-rolls with `kafkaml_datasources.RawSink` directly (construct a
`RawSink`, loop `sink.send(data=x, label=y)` over the rows, `.close()` -
which is what actually registers the datasource, via the control-topic
message `kafka_control_logger` forwards to the backend), collapsed into
one call. `send_dataset(bootstrap_servers, topic, deployment_id, data,
labels, **kwargs)` takes two array-likes (numpy `ndarray`, or pandas
`Series`/`DataFrame` converted via `.to_numpy()`); `send_dataframe(...,
dataframe, label_column)` is a convenience wrapper for a single
`DataFrame` holding both features and label in one table.

**Answers the "datasource creation helpers" gap this file's own Status
section used to flag** - a caller no longer needs `kafkaml-datasources`
as a *second*, separately-installed dependency to fully drive an
end-to-end flow through just this package.

Gated behind the `datasets` extra (`pip install kafkaml-client[datasets]`,
pulling in `kafkaml-datasources` + `numpy` + `pandas`), not a base
dependency - every import of these three is done lazily, inside the
functions themselves, so `import kafkaml_client` and the plain REST
`KafkaMLClient` usage never require any of them. `kafkaml-datasources` is
wired in via a local `path` source (`[tool.uv.sources]`), same monorepo
pattern `tf-kafka-dataset`'s two consumers already use - not how a real
external release would resolve it.

`send_dataset` checks `len(data) == len(labels)` **before** constructing
the underlying `RawSink` (and therefore before any Kafka client exists at
all) - a mismatch fails immediately and cleanly rather than partway
through a real send, or worse, silently truncating via `zip`. If a *later*
row-level send does fail mid-stream (a row that isn't actually
array-shaped, say), the sink's `.close()` still fires from a `finally` -
a partial send still gets registered with whatever `total_msg` it
actually reached, rather than leaving already-published Kafka data
completely unregistered and orphaned.

Tested (`tests/test_datasets.py`, 10 tests) against a faked
`kafka.KafkaConsumer`/`KafkaProducer` (`tests/conftest.py`'s
`patch_kafka` fixture - duplicated from, not shared with, `../datasources/
tests/conftest.py`'s equivalent, since it's a handful of lines and this
suite shouldn't depend on that package's test layout) - but with **real**
numpy arrays and pandas `DataFrame`/`Series` as the actual dataset
objects sent through, so the tests exercise the genuine duck-typing
contract `RawSink` expects (`type(x).__name__` containing `"ndarray"`),
not a hand-wavy stand-in for it. The fake consumer's `end_offsets` counts
real messages the paired fake producer sent, rather than returning a
constant - otherwise `total_msg` in the control message would always
read 0 regardless of how many rows were actually sent, silently
defeating any test that checks it.

## Real-time inference request/response support (2026-08-07)

`kafkaml_client.predictions.predict_one`/`predict_batch` (also exposed as
`KafkaMLClient.predict_one`/`.predict_batch`) close the loop on the
*other* side of a deployment: `send_dataset` gets training data in,
these send input row(s) to a deployed real-time inference's input topic
and read the prediction(s) back from its output topic - the same flow
every `examples/*/*_dataset_inference_example.py` script hand-rolls with
a plain `kafka.KafkaProducer`/`KafkaConsumer` pair (there's no dedicated
class for this in `kafkaml_datasources` either - it only has
`AvroInference`, for AVRO; RAW-format inference I/O is just plain Kafka
topics by design). `predict_batch` takes a list of rows and returns
predictions in send order (matching a single-partition input/output
topic, the standard shape for a Kafka-ML deployment); `predict_one` is
`predict_batch` for exactly one row. Same `datasets` extra as
`send_dataset` (now lists `kafka-python` explicitly too, not just
transitively via `kafkaml-datasources` - `predictions.py` imports `kafka`
directly, it doesn't go through `RawSink`).

**Bakes in a real bug's fix by construction**: the output consumer is
always built with `auto_offset_reset="earliest"`, not `kafka-python`'s
own `"latest"` default. A consumer created with the default can join its
consumer group *after* a fast real-time inference deployment has already
produced the prediction(s), and silently see nothing - this is the exact
bug found (and fixed, in 6 places) in this project's own
`examples/*/*_dataset_inference_example.py` scripts on 2026-08-07 (see
`FUTURE.md`). Rather than leave a caller of this SDK exposed to the same
trap, the fix is unconditional here, not a keyword a caller could forget
to pass.

Tested (`tests/test_predictions.py`, 8 tests) against a faked
`kafka.KafkaConsumer`/`KafkaProducer`, patched at the `kafka` module
itself (not `kafkaml_datasources.sink`, which `send_dataset`'s tests
patch instead) - `predictions.py` imports `kafka.KafkaConsumer`/
`KafkaProducer` directly inside its own function bodies, re-resolving
them from the `kafka` module on every call, so that's the patch target
that actually takes effect. Since neither fake simulates a real
deployment's consume-and-publish loop, tests install a small
`_echo_predictions_on_send` helper that makes every send to the input
topic immediately produce a matching, test-controlled prediction on the
output topic - standing in for "a real deployment handled this input,"
which nothing in the fakes does on their own. Covers order-preservation
across a batch, the `TimeoutError` path (fewer predictions arrive than
rows sent), pandas-row support, and - directly - that
`auto_offset_reset="earliest"` is what's actually passed to the
consumer.

## Design notes worth keeping if this is extended

- `create_model`/`create_configuration`/`create_deployment`/
  `deploy_inference` all have to **look the created object back up** after
  a successful `POST`, because none of `backend`'s create
  endpoints return the created row or an id in the response body (they
  return `201` with an empty body, matching the Django reference's
  contract - not something to "fix" here, just something this client has
  to work around). `create_model`/`create_configuration` look up by
  `name` (assumes unique names - true for every real Kafka-ML model/
  configuration, since the DB has a unique constraint on both); `deployment`/
  `inference` creation instead diffs the id set before/after, since
  deployments and inferences have no unique human-chosen name to search
  by.
- `create_deployment`'s `**fields` passthrough deliberately does **not**
  enumerate every possible field as a typed keyword argument - the
  backend's own `_PASSTHROUGH_FIELDS` list (`app/controllers/deployments.py`)
  is long and framework/mode-dependent (TensorFlow vs. PyTorch kwargs use
  different key *names*, not just different values; incremental/
  distributed/federated modes each need their own extra fields). A fixed
  set of typed parameters would either be incomplete or need constant
  upkeep as the backend's own contract evolves - passthrough plus a
  docstring reference is the more honest contract for a draft SDK.
- `wait_for_results` raises `TimeoutError` (not a `KafkaMLError`) on
  timeout, matching Python's own convention for "waited too long" rather
  than treating it as an HTTP-layer error - it isn't one.

## Status

Draft/PoC, not a polished, versioned SDK - no retries/backoff beyond the
one polling loop, no async client, no typed response models (dicts
straight from the JSON body, matching the backend's own loose
`dict[str, Any]` request/response style - see `backend/CLAUDE.md`
for why that's a deliberate choice on the backend side too). If this gets
adopted for real, still worth adding: IoT device / websocket visualization
coverage (still unwrapped, see "What it wraps" above), typed
dataclasses/TypedDicts for the response shapes, and async support to
match `backend`'s own fully-async design.
