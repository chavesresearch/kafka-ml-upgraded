---
sidebar_position: 1
---

# backend

`backend/` is the REST API and Kubernetes orchestrator at the center of
Kafka-ML. It stores every model/configuration/deployment/result, talks to
the `mlcode_executor` services to validate submitted model code, and
creates the real Kubernetes `Job`/`Deployment`/`ReplicationController`
objects that do training and inference. Everything in
[Usage](../usage/single-models) and the [SDK](/sdk/intro) ultimately calls
this service.

This page is about how the module is built internally — for how to use
the API, see the [SDK docs](/sdk/intro) or the Web UI tutorials in
[Usage](../usage/single-models).

## Stack

Litestar 2.x (async request handlers) + SQLAlchemy 2.0 async (via
`aiosqlite`, the same single-file `db.sqlite3` the project has always
used) + Alembic migrations + `kubernetes-asyncio` for cluster access +
`httpx.AsyncClient` for calling the code-executor services +
`aiokafka` for a single consumer-only use (the `/ws/` visualization
relay — this backend has no Kafka *producer* at all, see below).

This is a from-scratch async port of an earlier Django/DRF
implementation, kept as a historical reference in a separate sibling
checkout outside this repository. The port deliberately kept the same
URL paths, JSON field names, and status codes so the frontend didn't
need to change — it's a different stack behind the identical contract,
not a redesigned API.

## Layout

| Path | Purpose |
|---|---|
| `app/config.py` | Environment-driven settings (same env var names the previous Django backend used, so Kubernetes manifests didn't need to change). |
| `app/models.py` | SQLAlchemy ORM models. A `before_flush` event listener bumps a `status_changed` timestamp column whenever a `TrainingResult`/`Inference` row's `status` changes — reproducing a Django `MonitorField` behavior the frontend depends on. |
| `app/db.py` | Async engine + `provide_db_session` dependency. **One transaction per request**: `session.begin()` wraps the whole request handler, so if anything fails partway through — including a Kubernetes API call inside a handler — the DB writes for that request roll back automatically. There's no manual compensating-delete logic anywhere; failures are handled by letting the exception propagate and the transaction abort. |
| `app/clients.py` | The shared `httpx.AsyncClient`, provided through DI, used to call `mlcode_executor`. |
| `app/schemas/__init__.py` | Plain-function response dict builders — one function per resource shape, field-for-field equivalents of the old serializer classes. |
| `app/controllers/*.py` | Route handlers, one module per resource: `models.py`, `configurations.py`, `deployments.py`, `training_results.py`, `inferences.py`, `datasources.py`, `iot_devices.py`. Request bodies are typed `dict[str, Any]`, not per-field structs — a deliberate choice to mirror the original's manual `json.loads(request.body)` validation style rather than adding strict typed validation the old contract never had. |
| `app/job_manifest_generator.py` | Builds the Kubernetes Job manifests (training containers) from a deployment's parameters. |
| `app/blockchain.py` | ERC20 token deployment for the optional `ENABLE_FEDML_BLOCKCHAIN` feature, using a precompiled contract artifact under `app/contracts/`. |
| `app/websocket.py` | The `/ws/` Kafka→browser visualization relay. |
| `app/utils.py` | Shared helpers, including `kubernetes_api_client()` — the function that builds an in-cluster `kubernetes_asyncio.client.ApiClient`. |
| `app/main.py` | App wiring: routes, CORS, DI providers, startup/shutdown lifecycle. |
| `migrations/` | Alembic, with an async `env.py` (`async_engine_from_config` + `run_sync`) — migrations are committed here, unlike the old Django app's uncommitted `makemigrations` output. |

## Request lifecycle

A typical write request (e.g. `POST /deployments/{configuration_id}`) flows
through:

1. Litestar resolves the route in `app/controllers/deployments.py` and
   injects the DB session and shared `httpx.AsyncClient` via DI.
2. `provide_db_session` opens `session.begin()` for the whole handler —
   every read/write inside the function shares one transaction.
3. The handler reads/writes ORM rows through `app/models.py`, and, for a
   deployment, builds a Kubernetes Job manifest via
   `app/job_manifest_generator.py` and submits it through
   `kubernetes_asyncio`.
4. If the Kubernetes call fails after DB rows were already written in the
   same request, the whole transaction rolls back when the exception
   propagates out of the handler — there is no explicit
   `except: db.delete(...)` cleanup path.
5. The handler returns a plain dict built by a function in
   `app/schemas/__init__.py`, matching the old serializer's exact JSON
   shape.

## Kubernetes access

Kubernetes access is lazy, not eager: `load_incluster_config()` is called
per-request inside the handlers that need it (`deployments.py`,
`inferences.py`), not once during app startup. Calling it eagerly in the
Litestar lifespan would make the whole pod fail to boot if the Kubernetes
API isn't reachable the instant the pod starts — a real risk since
Kubernetes doesn't guarantee pod startup order.

`kubernetes_asyncio.config.load_incluster_config` is a **synchronous**
function even though the rest of the client is async — it must be called
directly, not `await`ed. Building the `ApiClient` for in-cluster calls
must also be done with **no** `Configuration` argument (`app/utils.py`'s
`kubernetes_api_client()`) — `ApiClient.__init__` falls back to
`Configuration.get_default_copy()` internally only when no configuration
object is passed, and that's what actually picks up the in-cluster
defaults `load_incluster_config()` registered. Passing a freshly
constructed, empty `client.Configuration()` instead silently targets
`http://localhost` (its hardcoded default `_base_path`), so every
in-cluster call would go nowhere. The identical helper (and the identical
bug, independently found and fixed) exists in
`federated-module/federated_backend/app/kubernetes_deploy.py` — see the
[federated-module page](./federated-module).

## Talking to `mlcode_executor`

Before a model is accepted (create or edit), `app/controllers/models.py`
calls the matching `tfexecutor`/`pthexecutor` service over plain HTTP
(via the shared `httpx.AsyncClient`) to `exec()` the submitted code and
confirm it defines a valid model. This is a real network call between two
services, not an in-process import — see the
[mlcode_executor page](./mlcode-executor) for what happens on the other
end.

## The `/ws/` visualization relay

`app/websocket.py` implements the Web UI's live prediction visualization.
A browser opens a Litestar `WebSocket` connection to `/ws/`, then sends
`{"topic": "...", "classification": true|false}`. The handler spins up a
plain `asyncio.Task` per subscription — one `aiokafka` consumer per
connected browser tab, relaying messages from the requested output topic
straight to the socket. There's no Django-Channels-style channel layer;
it's native Litestar WebSocket support over raw ASGI messages, and no
shared broker-side fan-out — each browser gets its own Kafka consumer
instance.

## Why there's no Kafka producer in this backend

Earlier in this port's history, `POST /datasources/` re-published every
incoming payload back onto the Kafka control topic ("so training jobs
pick it up"). That endpoint is only ever called by
`kafka_control_logger`, which itself reached the backend *because* it had
just consumed a message from that same control topic — republishing
created an unbounded feedback loop where `kafka_control_logger` would see
its own round-trip and forward it again forever. Training Jobs already
consume the control topic directly and filter by deployment id, so the
republish added no information they didn't already have. It was removed
entirely — `_create_datasource` in `app/controllers/datasources.py` is
now pure DB persistence, and the backend has no Kafka producer or
`kafka_producer` DI dependency at all.

## Multipart uploads and Litestar's `data` parameter

Litestar reserves the name `data` for the request-body parameter
(`litestar.constants.RESERVED_KWARGS`). A handler parameter named
anything else is silently treated as a plain query parameter instead —
no error is raised about the mismatched body annotation, just a
confusing `Missing required query parameter` `ValidationException` at
request time. This matters for `training_results.py`'s multipart trained
-model upload handler, which is annotated
`Annotated[SomeStruct, Body(media_type=RequestEncodingType.MULTI_PART)]`
on a parameter literally named `data`.

## A wire contract that looks like a typo but isn't

The multipart field name `confussion_matrix` (missing an "o") in the
training-result upload endpoint is a real wire contract, not a bug to
fix — `model_training`'s training containers send that exact
(misspelled) field name. Renaming it here would silently break every
training container currently deployed.

## Route disambiguation

Litestar correctly disambiguates static path segments from typed
parameters purely from path shape — `/results/chart/{result_id:int}`
never collides with `/results/{result_id:int}` (different path depth),
and a literal segment like `/models/distributed` doesn't collide with
`/models/{model_id:int}` because `"distributed"` fails `int` conversion
and Litestar backtracks to the static route. No explicit ordering is
needed when registering `Router(route_handlers=[...])`.

## Two endpoints that are intentionally asymmetric

`GET /deployments/{pk:int}` treats `pk` as a **Configuration** id (it
lists that configuration's deployments); `DELETE` on the *same path*
treats `pk` as a **Deployment** id instead. This looks like a bug but is
the deliberately preserved existing contract — the frontend already
relies on it, so it isn't "fixed" by splitting the route.

## Testing

`tests/` is a real pytest suite run with `uv run pytest -v`, using
Litestar's `TestClient` against a temp-file SQLite database created once
per session (no live cluster or Kafka broker required). Calls into the
code executor are mocked (`patch('app.controllers.models._check_model_code', ...)`
). Kubernetes manifest generation and actual deployment behavior are
**not** covered by this suite — they've only ever been verified against a
real cluster, which the tests don't attempt.

## See also

- [federated-module](./federated-module) — a satellite service that
  independently talks to Kubernetes with the same
  `kubernetes_api_client()`-shaped fix.
- [mlcode_executor](./mlcode-executor) — the service `app/controllers/models.py`
  calls to validate model code.
- [kustomize](./kustomize) — the manifests that deploy this service and
  the Jobs it creates.
