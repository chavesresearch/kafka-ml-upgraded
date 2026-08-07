---
sidebar_position: 8
---

# kafkaml-client

`kafkaml-client/` is `kafkaml_client`, a small installable Python package
(`src/` layout, `uv_build`) wrapping the Kafka-ML `backend` REST API — an
alternative to driving `backend` with hand-rolled HTTP calls or the Web
UI. It's a draft/proof-of-concept, not a versioned 1.0 SDK: no retries
beyond the polling loop, no async client, no typed response models
(every method returns plain `dict`/`list[dict]` straight from the JSON
body).

This page covers how the package is built internally — packaging, the
HTTP layer, testing. **For the public API itself (every method,
arguments, return values, usage examples), see the separate
[SDK reference site](/sdk/intro)** — this page deliberately does not
re-explain method signatures already documented there.

## Where the logic came from

The client's logic was lifted out of `integration-tests/common.py`,
which needed almost exactly this — build a model/configuration/deployment
payload, `POST` it, look the created object back up (these endpoints
don't return it), poll `/results/` until a status is reached — for its
own test suite. Rather than leave that logic buried in a test helper, it
was extracted into this standalone package, and `integration-tests/common.py`
was then rewritten to depend on it. That means every real
model/configuration/deployment/inference create exercised by
`integration-tests/` (TF CASE 1-4, PyTorch, inference) goes through this
package's actual code, not a bypassed path.

## Package layout

```
kafkaml-client/
├── src/kafkaml_client/
│   ├── __init__.py     # re-exports KafkaMLClient, KafkaMLError
│   ├── client.py        # the REST client
│   └── datasets.py      # optional numpy/pandas -> Kafka datasource support
├── tests/
│   ├── conftest.py       # FakeBackend + httpx.MockTransport, plus Kafka fakes
│   ├── test_client.py
│   └── test_datasets.py
└── pyproject.toml
```

The REST client lives in one module, `client.py` — there's no separate
models/resources/transport split. `KafkaMLClient` is a single class with
one method group per backend resource (models, configurations,
deployments, results, inference), plus two internal helpers (`_request`,
`_find_id_by_name`). `datasets.py` is a separate module on purpose — see
"Sending datasets" below.

## The HTTP layer

`KafkaMLClient.__init__(base_url, timeout=30)` builds one `httpx.Client`
(stored as `self._http`) for the lifetime of the object; the class
supports use as a context manager (`with KafkaMLClient(...) as c:`) to
close that connection pool automatically, or a manual `.close()`. There
is no dependency-injection point for the underlying transport — every
public method funnels through a single `_request(method, path, **kwargs)`
helper that calls `self._http.request(...)` and raises `KafkaMLError`
(carrying `status_code` and `response_text`) for any response with
`status_code >= 400`.

Two recurring patterns sit on top of that helper because of how
`backend`'s create endpoints behave — they return `201` with an empty
body, not the created row or its id:

- `create_model`/`create_configuration` look the created object back up
  by **name** right after the `POST` (`_find_id_by_name`), relying on
  the backend's unique-name constraint on both resources.
- `create_deployment`/`deploy_inference` have no unique human-chosen name
  to search by, so instead they snapshot the id set before the `POST`
  and diff it against the id set after, returning whichever id is new.

`create_deployment(configuration, batch=1, **fields)` passes `fields`
straight through as the JSON body rather than enumerating every possible
deployment field as a typed keyword argument — the backend's own
accepted-field list is long, framework-dependent (TensorFlow vs. PyTorch
use different kwarg *names*), and mode-dependent (incremental/
distributed/federated each need their own extra fields). A fixed
parameter list would either be incomplete or need constant upkeep as
that contract evolves.

`wait_for_results` raises a plain `TimeoutError` on timeout rather than
`KafkaMLError` — a deliberate distinction, since "waited too long" isn't
an HTTP-layer failure.

## What it does and doesn't cover

It wraps `/models/`, `/configurations/`, `/deployments/`, `/results/`,
`/results/inference/{id}`, and `/inferences/{id}` — the core CRUD plus
the training-completion polling loop — and, via `send_dataset`/
`send_dataframe` (below), sending an actual dataset to Kafka and
registering it as a datasource. It does not wrap IoT device endpoints or
the `/ws/` visualization relay.

## Sending datasets

Datasource registration doesn't go through the REST API at all — it
happens when a `kafkaml_datasources.RawSink` is `.close()`d, which
publishes a control-topic message that `kafka_control_logger` forwards
to `backend`'s `POST /datasources/`. Every
`examples/*/*_dataset_training_example.py` script in this repo
hand-rolls that same pattern directly (construct a `RawSink`, loop
`sink.send(data=x, label=y)` over the rows, `.close()`).
`kafkaml_client.datasets.send_dataset`/`send_dataframe` — also exposed
as `KafkaMLClient.send_dataset`/`.send_dataframe` — collapse it into one
call, accepting numpy `ndarray`s or pandas `Series`/`DataFrame`s
directly (converted via `.to_numpy()`):

```python
client.send_dataset(
    "localhost:9094", topic="my-topic", deployment_id=deployment_id,
    data=X, labels=y,
)
# or, for a single DataFrame holding both features and label:
client.send_dataframe(
    "localhost:9094", topic="my-topic", deployment_id=deployment_id,
    dataframe=df, label_column="y",
)
```

This needs the `datasets` extra (`pip install kafkaml-client[datasets]`,
pulling in `kafkaml-datasources` + `numpy` + `pandas`) — every import of
those three happens lazily, inside `datasets.py`'s functions, so plain
`import kafkaml_client` and REST-only usage never require any of them.
`kafkaml-datasources` is wired in via a local `path` source
(`[tool.uv.sources]`), the same monorepo pattern
[tf-kafka-dataset](./tf-kafka-dataset)'s consumers use.

`send_dataset` checks `len(data) == len(labels)` before constructing the
underlying `RawSink` — a mismatch fails immediately, before any Kafka
client exists, rather than partway through a real send or silently
truncating via `zip`. If a row-level send *does* fail mid-stream, the
sink's `.close()` still runs from a `finally` block, so a partial send
still gets registered with whatever row count it actually reached,
rather than leaving already-published Kafka data completely
unregistered.

## Testing approach

`tests/` (`uv run pytest -v`, CI via `.github/workflows/kafkaml-client.yml`)
uses a small in-memory `FakeBackend`, wired in through
`httpx.MockTransport` — httpx's own supported mechanism for testing
client code without a real server. Because `KafkaMLClient.__init__`
builds its own `httpx.Client` with no injection point, the test fixture
constructs a real client normally and then swaps its private `_http`
attribute for one backed by the mock transport; this reaches into a
"private" attribute deliberately, treated as acceptable for a documented
draft/PoC rather than adding dependency-injection machinery for one
fixture. `FakeBackend`'s status codes mirror the real Litestar contract
(`POST` → 201, `DELETE` → 204, `stop_inference`'s `POST` → 200 since it
acts on an existing resource rather than creating one).

The suite covers this client's own logic — id-lookup-after-create,
before/after id-diffing, `KafkaMLError` wrapping, and
`wait_for_results`' polling/timeout/`min_results` behavior — not the
real backend's behavior (that's `backend/tests`' job). It's pinned to
`pytest==8.4.2` rather than the `9.x` used by the single-controlled-
Docker-image service projects elsewhere in the repo, since this
package's own `requires-python = ">=3.9"` is a real compatibility
promise to external callers and `pytest 9` dropped Python 3.9 support.

`test_datasets.py` (10 more tests) covers `send_dataset`/`send_dataframe`
against a faked `kafka.KafkaConsumer`/`KafkaProducer` — but with real
numpy arrays and pandas `DataFrame`/`Series` as the actual dataset
objects sent through, exercising the genuine duck-typing contract
`RawSink` expects rather than a stand-in for it. The fake consumer's
`end_offsets` counts real messages the paired fake producer sent (rather
than a constant), since `RawSink`'s `total_msg` control-message field is
computed from that offset diff — a constant would silently make any
`total_msg` assertion meaningless regardless of how many rows were
actually sent.

## Status

Draft/PoC. If it's adopted more broadly, natural next steps (not yet
done) would be IoT device / websocket visualization coverage, typed
response models, and an async client to match `backend`'s own
fully-async design.

## See also

- [/sdk/intro](/sdk/intro) — the public API reference for this package:
  every method, its arguments, and usage examples.
- [backend](./backend) — the REST API this package wraps.
- [datasources](./datasources) — the complementary package for sending
  actual training/inference data into Kafka.
- [model-training](./model-training) / [model-inference](./model-inference) —
  what a deployment created through this client actually runs.
