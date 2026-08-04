# Kafka-ML Litestar backend — instructions for AI assistants

This is a from-scratch async port of the original Django/DRF backend,
whose source is preserved at `../../kafka-ml/backend` (a separate,
git-tracked sibling checkout kept purely as historical reference — it is
not deployed and not part of this repo). The Django app is the
**reference implementation for behavior** — same URL paths, same JSON
field names, same status codes, so the Vue frontend works unchanged. When
in doubt about what an endpoint should do, read the matching view under
`../../kafka-ml/backend/automl/views/<name>.py` and its serializer in
`../../kafka-ml/backend/automl/serializers.py`. Don't "improve" the API
shape without being asked; the frontend depends on exact field names.

**Status: this is the deployed backend.** It was cut over from the Django
implementation (which used to live at this same path, `backend/`) after
being verified functionally complete — see `kustomize/base/resources/
backend-deployment.yaml`, which points at this port's image.

## Stack (do not swap pieces without being asked)

- [Litestar](https://litestar.dev/) 2.x — async request handlers throughout
- SQLAlchemy 2.0 (async) + `aiosqlite` — same single-file local `db.sqlite3`
  the Django backend used
- Alembic — migrations are meant to be committed here (unlike Django's
  `makemigrations`, which the old backend never committed)
- `aiokafka` — consumer only (`/ws/` relay). There's no Kafka producer in
  this backend (see the removed-republish note below) - datasource creation
  is pure DB persistence.
- `kubernetes-asyncio` — Job/ReplicationController management
- `httpx.AsyncClient` — calls to the tf/pth `mlcode_executor` services
  (also ported to Litestar, see `../mlcode_executor/CLAUDE.md`; still
  plain HTTP between the two services, not an in-process call)
- Native Litestar `WebSocket`, no channel layer — the `/ws/` relay is a
  plain `asyncio.Task` per subscription, not Django Channels

## Layout

| Path | Purpose |
|---|---|
| `app/config.py` | Environment-driven settings, equivalent of `autoweb/settings.py`. Same env var names as the Django backend (see README) so kustomize manifests don't need to change. |
| `app/models.py` | SQLAlchemy models, equivalent of `automl/models.py`. Includes a `before_flush` event listener that reproduces django-model-utils' `MonitorField` (bumps `status_changed` whenever `status` changes on `TrainingResult`/`Inference`). |
| `app/db.py` | Async engine + `provide_db_session` dependency. **One transaction per request** (`session.begin()` wraps the whole handler) — a deliberate improvement over Django's per-statement autocommit: if anything fails partway through (e.g. a Kubernetes call in `deployments.py`), the whole request's DB writes roll back automatically. Don't add manual compensating deletes; let exceptions propagate. |
| `app/clients.py` | The shared `httpx.AsyncClient`, provided via DI. |
| `app/schemas/__init__.py` | Plain-function response dict builders, field-for-field equivalents of `automl/serializers.py`'s `ModelSerializer` classes. Add a new field here (not a new abstraction) when a model gains one. |
| `app/controllers/*.py` | Route handlers, one module per resource, equivalent of `automl/views/*.py`. Request bodies are typed `dict[str, Any]` (not per-field structs) to mirror the original's own `json.loads(request.body)` + manual validation style — this was a deliberate choice for a faithful port, not an oversight. |
| `app/job_manifest_generator.py` | Kubernetes Job manifest builders. Ported **unchanged** from `automl/views/utils/job_manifest_generator.py` — it never depended on Django, just takes a `settings`-like object. |
| `app/blockchain.py` | ERC20 token deployment for the optional `ENABLE_FEDML_BLOCKCHAIN` feature. Contract sources are under `app/contracts/` (copied from the old Django backend's `autoweb/contracts/`, preserved at `../../kafka-ml/backend/autoweb/contracts/`). |
| `app/websocket.py` | The `/ws/` Kafka→browser visualization relay. |
| `app/main.py` | App wiring: routes, CORS, DI providers, startup/shutdown lifecycle. |
| `migrations/` | Alembic; `env.py` is async (`async_engine_from_config` + `run_sync`). |

## Gotchas learned the hard way (keep these)

1. **Litestar's request-body parameter must be named `data`.** It's one of
   `RESERVED_KWARGS` (`litestar.constants`) — annotate it with
   `Annotated[SomeStruct, Body(media_type=RequestEncodingType.MULTI_PART)]`
   (or `URL_ENCODED`) same as any other param, but if you name it anything
   else (e.g. `payload`), Litestar silently treats it as a plain **query**
   parameter instead and you get a confusing `Missing required query
   parameter` `ValidationException` — no error about the mismatched body
   annotation at all. Hit this once in `training_results.py`'s multipart
   upload handler; caught it via the smoke test, not by inspection.
2. **`web3==5.28.0` (kept for the blockchain feature) pins `websockets<10`;
   `uvicorn[standard]` pins `websockets>=10.4`.** These directly conflict.
   Fix: don't install `uvicorn[standard]`; install plain `uvicorn` +
   `wsproto` + `httptools` and run with `--ws wsproto` (see `start.sh`).
   Litestar itself doesn't need the `websockets` package — it implements
   WebSocket over raw ASGI messages.
3. **`web3`'s `ipfshttpclient==0.8.0a2` dependency is a pre-release** —
   installs need `prerelease = "allow"`, set once in `pyproject.toml`'s
   `[tool.uv]` table rather than a flag you have to remember to pass every
   time (matches the `--prerelease=allow` flag the original `backend/
   Dockerfile` used).
4. **`msgspec==0.18.6` has no prebuilt wheel for Python 3.13** and fails to
   *compile* from source against it (3.13 removed/changed private C API
   symbols like `_PyLong_AsByteArray`'s signature) — `uv add`/`uv lock` will
   pick whatever Python `uv` defaults to (which may float to 3.13+ if you
   don't pin one) and this build error is what you'll hit. `requires-python
   = ">=3.12,<3.13"` in `pyproject.toml` pins it away; if you ever bump
   `msgspec` past this, re-check whether the upper bound is still needed.
5. **`greenlet` must be an explicit dependency.** SQLAlchemy's async ORM
   needs it even with a fully-async driver like `aiosqlite` (it bridges the
   sync unit-of-work internals), but plain `sqlalchemy` (without the
   `[asyncio]` extra) doesn't pull it in — you get `ValueError: the
   greenlet library is required` at the first `session.begin()`.
6. **The Kubernetes client connects lazily, not at app startup.**
   `kubernetes_asyncio.config.load_incluster_config()` run eagerly in the
   app lifespan would make the whole pod fail to boot if Kubernetes isn't
   reachable yet — a real risk given Kubernetes doesn't guarantee pod
   startup order. Kubernetes calls are made per-request inside the handler
   instead — don't move `load_incluster_config()` into the lifespan.
   (There used to be an equivalent note here about a lazily-connecting
   Kafka producer for datasource creation - removed along with the producer
   itself, see the bug list below.)
7. **The multipart field name `confussion_matrix` (misspelled, missing an
   "o") is a real wire contract**, not a typo to fix — `model_training/
   tensorflow/mainTraining.py` and friends send exactly that field name to
   `POST /results/{id}`. Renaming it here would silently break every
   training container, which this rewrite doesn't touch.
8. **Litestar disambiguates static path segments from typed params
   correctly** — e.g. `/results/chart/{result_id:int}` vs
   `/results/{result_id:int}` never collide because they're different path
   depths, and `/models/distributed` (literal) vs `/models/{model_id:int}`
   don't collide because `"distributed"` fails `int` conversion and
   Litestar backtracks to the static route. No special ordering needed in
   `Router(route_handlers=[...])`.

## Bugs found in the Django backend and fixed here

Don't reintroduce these while porting more of the old Django backend's
history (`../../kafka-ml/backend`) or cross-checking behavior:

1. `settings.DEVICES_ROOT` / `TFLITE_PARSED_MODELS_DIR` were referenced by
   IoT device code (`automl/serializers.py`, `automl/views/iot_devices.py`)
   but **never defined anywhere** — creating an IoT device or deploying a
   model to one crashed with `AttributeError`. Now defined in
   `app/config.py`.
2. `GET /models/result/{id}` was dead: `automl/views/models.py`'s
   `ModelResultID` class defined `get()` **twice** in the same class body;
   Python keeps only the second, silently shadowing the correct
   implementation with ~90 lines of copy-pasted `InferenceResultID` logic
   that returned the wrong JSON shape. The frontend's `getModelResultID()`
   (inference views) was getting `{input_format, input_config}` instead of
   an `MLModel`. Fixed in `app/controllers/models.py`.
3. `Datasource` rows were validated (`DatasourceSerializer(data=data)`) but
   **never `.save()`d** in either `DatasourceList.post` or
   `DatasourceToKafka.post` — the table was permanently empty, so
   `GET /datasources/` and the input-format lookups in `InferenceResultID`
   that filter on it never had anything to find. Now persisted in
   `app/controllers/datasources.py`.
4. The Kafka control-topic message key was `bytes([deployment_id])` — caps
   deployment ids at 255, raises `ValueError` above that. This code path
   (the backend's own control-topic publish) no longer exists at all - see
   #7 below - so the fix now lives at the actual source instead: the
   `KafkaMLSink` client library (`../datasources`) widens its deployment-id
   key encoding to 4 bytes big-endian. Every consumer (`model_training/*`,
   `mlcode_executor/tfexecutor/app.py`, `kafka_control_logger`) decodes it
   generically via `int.from_bytes(msg.key, byteorder="big")`, so this
   stays wire-compatible regardless of key width.
5. `DatasourceList.post` and `DatasourceToKafka.post` were byte-for-byte
   duplicated code; deduped into one handler mounted at both routes.
6. `autoweb/create_blockchain_token.py` resolved its Solidity contract path
   via `os.getcwd()` — only worked if the process's cwd happened to match
   the Docker `WORKDIR`. `app/blockchain.py` anchors it to the module's own
   file location instead.
7. **`POST /datasources/` re-published every payload back onto
   `CONTROL_TOPIC`** ("so training jobs pick it up" - the original,
   plausible-sounding rationale, kept in the Django version too). This is
   an unbounded feedback loop: this endpoint is only ever called by
   `kafka_control_logger`, which itself got the message by consuming
   `CONTROL_TOPIC` in the first place (client-side `KafkaMLSink.close()`
   publishes there directly). Re-publishing back onto the same topic means
   `kafka_control_logger` sees its own round-trip and forwards it again -
   every datasource submission would duplicate its `Datasource` row and
   re-publish to Kafka forever, with nothing ever breaking the cycle.
   Training jobs (`model_training/*`) already consume `CONTROL_TOPIC`
   directly and filter by the deployment-id key, so the republish added no
   information they didn't already have. Removed entirely - `app/
   controllers/datasources.py`'s `_create_datasource` is now pure DB
   persistence, no Kafka producer involved (`app/clients.py`'s
   `LazyKafkaProducer` and the `kafka_producer` DI dependency were removed
   as a result - nothing else used them). If you're auditing
   `../../kafka-ml/backend` (Django) or old deployment configs: this loop
   is still live there: it wasn't in scope to patch the reference
   implementation, only this port.
8. **`POST /datasources/` passed `data["time"]` (a JSON string) straight
   into `Datasource(time=...)`** - works fine against the Django
   `DatasourceSerializer`, which has a typed `DateTimeField` that parses
   ISO 8601 strings automatically, but this port's controllers take
   `data: dict[str, Any]` and skip that typed validation entirely (a
   deliberate choice, see the "Layout" table above) - so the raw string
   reached SQLAlchemy directly, which raised `TypeError: SQLite DateTime
   type only accepts Python datetime and date objects as input` at flush
   time for *every* call. `GET /datasources/` never surfaced this because
   no row had ever successfully been created (bug #3 above meant the table
   was permanently empty until this session, so nothing had exercised this
   path with a real insert). Fixed with `datetime.fromisoformat(data["time"])`
   in `app/controllers/datasources.py`. This makes `kafka_control_logger`'s
   output format a real wire contract now: it must send a
   `datetime.isoformat()`-produced string (or anything else
   `datetime.fromisoformat` accepts - `Z`-suffixed UTC works too on
   Python ≥3.11). Caught by actually inserting a row against a throwaway
   in-memory SQLite DB, not by inspection - worth doing for any other
   `dict[str, Any]` field that maps to a typed (non-string) column.
9. **Two real, previously-untested Kubernetes bugs, found only once an
   actual API-driven deployment was attempted against a live cluster**
   (this port's own smoke testing had never exercised Job/RC creation
   before, per the old note in gotcha #6 above):
   - `kubernetes_asyncio.config.load_incluster_config` is a **sync**
     function in `kubernetes-asyncio==32.0.0` (confirmed with
     `inspect.iscoroutinefunction` → `False`) — three call sites
     (`app/controllers/deployments.py`, `app/controllers/inferences.py`
     ×2) `await`ed it anyway, raising `TypeError: object NoneType can't be
     used in 'await' expression` on every single call. This meant no real
     Kubernetes deployment via the API had ever actually worked in any
     prior testing. Fixed by calling it plain (no `await`) at all three
     sites.
   - `app/utils.py`'s `kubernetes_api_client()`: building a bare
     `client.Configuration()` and handing it to `ApiClient()` does **not**
     inherit whatever `load_incluster_config()` registered as the
     process-wide default — `Configuration.__init__` hardcodes
     `self._base_path = "http://localhost"` whenever no `host` kwarg is
     given. Every in-cluster call (no token/external_host) was silently
     targeting `http://localhost` instead of the real API server. Fixed by
     calling `client.ApiClient()` with **no** `Configuration` argument at
     all in that branch — it resolves `Configuration.get_default_copy()`
     internally, which does pick up the in-cluster default. See the
     comment in `app/utils.py` for the full explanation; the exact same
     bug (byte-identical helper) was independently found in
     `federated-module`'s `federated_backend`.

## Things that look like bugs but are intentionally preserved for parity

- `GET /deployments/{pk:int}` treats `pk` as a **Configuration** id (lists
  its deployments); `DELETE` on the *same path* treats `pk` as a
  **Deployment** id. Confusing, but it's the existing
  `DeploymentsConfigurationID` contract — `frontend` already relies on it.
  Don't "fix" by splitting the route without checking the frontend first.
- `TrainingResult.train_metrics/val_metrics/test_metrics` default to `None`,
  not `{}`, matching Django's `JSONField(null=True)` with no explicit
  default — even though some downstream code (chart endpoint) assumes a
  dict once training starts reporting metrics. This only matters before a
  training job has posted its first metrics.
- `parse_kwargs_fit` still uses Python `eval()` on user-typed kwargs
  values. Not hardened, on purpose — it matches the app's existing trust
  model (the whole platform already `exec()`s user-submitted model code in
  `mlcode_executor`), and this wasn't in scope to change.
- Django admin (`/admin`) was **not** replicated. Confirmed via grep that
  neither frontend links to it — it was registered but unused.

## Testing approach

`tests/` is a real, committed pytest suite (16 tests, `test_models.py`/
`test_configurations.py`/`test_training_results.py` — mirrors the old
`../../kafka-ml/backend/automl/test_views.py`'s three themes, but against
this port's actual current contract, not the Django test's stale flat
`train_loss`/`val_loss` schema). Run it with:

```bash
uv run pytest -v
```

`tests/conftest.py` sets `DATABASE_URL` to a temp-file sqlite path and
creates the schema once per session — no real cluster or Kafka broker
needed. It uses Litestar's `TestClient` (`from litestar.testing import
TestClient`), not raw ASGI calls. For anything that calls the tf/pth
executor (`_check_model_code` in `app/controllers/models.py`), tests mock
it: `patch('app.controllers.models._check_model_code', new=AsyncMock(return_value=True))`.
For endpoints needing a `TrainingResult`/`Deployment` to exist without
going through the full k8s-dependent create flow, tests seed rows
directly via `app.db.async_session_maker()` (see `test_training_results.py`)
— use plain `asyncio.run(...)` from a sync test function for this, not an
`async def` test, since Litestar's `TestClient` manages its own event loop
per call and nesting that inside pytest-asyncio's loop risks a "loop
already running" conflict.

Two environment/tooling issues had to be worked around to get `pytest` to
even start in this venv (both from `web3==5.28.0`, kept only for the
optional blockchain feature, which none of the tests above exercise):
- `web3` registers a `pytest11` entry point
  (`web3.tools.pytest_ethereum.plugins`) that pytest auto-loads
  unconditionally for every run — its import chain does a bare
  `import pkg_resources` (removed by setuptools ≥81) and, once that's
  pinned away, `from inspect import getargspec` (removed in Python ≥3.11,
  via `eth_abi`→`parsimonious`). Fixed with `"setuptools<81"` in
  `pyproject.toml` plus `addopts = "-p no:pytest_ethereum"` in
  `[tool.pytest.ini_options]` — the latter disables only that one
  auto-loaded plugin, not all plugin autoloading (anyio's and faker's
  `pytest11` plugins still load fine).
- `from app.db import ...` doesn't resolve inside `tests/` without
  `pythonpath = ["."]` in `[tool.pytest.ini_options]` (no
  `tests/__init__.py`, no other project-root `sys.path` entry by default).

When adding new tests, confirm `alembic revision --autogenerate` produces
no unexpected diffs after model changes, and that `alembic upgrade head`
actually creates the tables — the pytest suite creates its schema via
`Base.metadata.create_all` directly, which won't catch a broken migration.

## Definition of done for any change here

1. Confirm the equivalent Django view/serializer (`../../kafka-ml/backend`)
   to check the exact field names and status codes expected — don't guess
   from the frontend alone.
2. Run `uv run pytest -v`; add or extend a test under `tests/` for the
   touched endpoint(s) — there's no CI wired up yet, so this suite is the
   only thing that will catch a regression.
3. If you touched `app/models.py`, generate a migration
   (`alembic revision --autogenerate -m "..."`) and run `alembic upgrade
   head` to confirm it applies cleanly — don't hand-edit the schema.
4. If you touched Kubernetes manifest generation
   (`app/job_manifest_generator.py`, `app/controllers/deployments.py` or
   `inferences.py`), there's no way to verify against a real cluster from
   the pytest suite alone (it never calls into `kubernetes_asyncio`) — say
   so explicitly rather than claiming it's tested, and see bug #9 above
   for what's gone wrong here before.
5. Keep `pyproject.toml`'s comments about the `setuptools`/`pkg_resources`
   pin, the `pytest_ethereum` plugin, and the `websockets`/`web3`
   conflict/`prerelease = "allow"` requirement intact if you touch
   dependencies — the reasons aren't obvious from the pins alone.
