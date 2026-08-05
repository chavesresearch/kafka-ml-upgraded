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
adopted for real, worth adding: datasource creation helpers (so a caller
doesn't need `kafkaml-datasources` *and* this package to fully drive an
end-to-end flow from one dependency), typed dataclasses/TypedDicts for the
response shapes, and async support to match `backend`'s own
fully-async design.
