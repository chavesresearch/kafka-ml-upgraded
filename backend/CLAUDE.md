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
| `app/blockchain.py` | ERC20 token deployment for the optional `ENABLE_FEDML_BLOCKCHAIN` feature. Contract sources are under `app/contracts/` (copied from the old Django backend's `autoweb/contracts/`, preserved at `../../kafka-ml/backend/autoweb/contracts/`), plus a new `Token.sol` (constructor-parameterized, see below) and a precompiled `app/contracts/Token.json` artifact - the deploy step loads that artifact and passes `token_name`/`token_symbol` as real constructor arguments, rather than compiling a dynamically-generated source string via `solcx` on every backend startup (see "Bugs found" below for why that changed). |
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
2. **`uvicorn[standard]` is still not installed, though the reason
   changed.** `web3==5.28.0` used to pin `websockets<10`, directly
   conflicting with `uvicorn[standard]`'s `websockets>=10.4` - that
   conflict is gone now that `web3` is `7.16.0` (pins
   `websockets<16.0.0,>=10.0.0`, no clash). Kept plain `uvicorn` +
   `wsproto` + `httptools` + `--ws wsproto` anyway (see `start.sh`) since
   it already works and Litestar doesn't need the `websockets` package
   itself (WebSocket is implemented over raw ASGI messages) - not worth
   churning a working setup for this alone, but this is no longer a
   forced choice if `uvicorn[standard]` is ever wanted for another
   reason.
3. **~~`web3`'s `ipfshttpclient==0.8.0a2` dependency is a pre-release~~ -
   gone.** That was a `web3==5.28.0`-era transitive dependency;
   `web3==7.16.0` (bumped 2026-08-05, see bug #10/#11 below) doesn't
   depend on `ipfshttpclient` at all, so `prerelease = "allow"` was
   removed from `pyproject.toml`'s `[tool.uv]` table entirely - installs
   are fully on stable releases now.
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
9. **`tests/conftest.py`'s schema-creation fixture only works if
   `app.models` has been imported somewhere first.** `Base.metadata` only
   knows about a table once the class defining it has actually been
   imported (class bodies register themselves as an import-time side
   effect) - `conftest.py` now imports `app.models` explicitly at its own
   top level specifically to guarantee this regardless of which test
   files happen to be selected. Found for real: running a subset of the
   suite that never imports model classes directly (only goes through the
   REST API - `test_configurations.py`/`test_deployments.py`) reliably
   collected an empty `Base.metadata`, so `create_all` silently created
   zero tables and every DB-touching call failed with
   `sqlite3.OperationalError: no such table`. The full suite always
   happened to include a file (`test_training_results.py`) that imports
   `app.models` at module level early enough to mask this - it looked
   like a flaky, timing-dependent bug until reproduced with a smaller,
   deliberately-chosen file selection. If you add a new test file that
   never imports `app.models`/`app.main` itself, this is still safe *only
   because* of the explicit import already in `conftest.py` - don't remove
   it as apparently-unused.

## Importing an already-trained model (2026-08-07)

`POST /deployments/import` (`app/controllers/deployments.py`) lets an
operator register an already-trained model for inference without a real
training Job - the platform's normal path is always Model ->
Configuration -> Deployment -> (real K8s training Job) -> finished
`TrainingResult`; this is the same chain with the Job step skipped and
the weights supplied directly. No schema change was needed: it just
creates a `Deployment` and one `TrainingResult` with `status="finished"`
up front, writes the uploaded file to the same
`{TRAINED_MODELS_DIR}/{result.id}.h5`/`.pth` convention `upload_result`
already uses, and every downstream consumer (real-time inference
deploy, IoT/TFLite deploy, download, chart view) works completely
unmodified - none of them know or care whether a result came from a
real training run or an import.

Scope, deliberately: only a **single (non-distributed) model**.
`configurations.py`'s `_expand_with_children` auto-expands a distributed
model's whole father/child chain into a configuration's `ml_models`, so
a distributed configuration always has >= 2 entries - checked explicitly
(and first, before the generic "exactly one model" length check, so the
error message names the real reason) rather than relying on the length
check to catch it as a side effect.

**The upload is validated before anything is persisted** - `POST`s the
file to the matching mlcode_executor service's new `/validate_model/`
endpoint (`tf.keras.models.load_model()` for TF; for PyTorch, `exec()`s
the model's own `code` to build the untrained module, then
`load_state_dict()`s the uploaded weights onto it) and only creates the
`Deployment`/`TrainingResult`/writes the file if that returns `200`. A
bad upload gets the real Keras/PyTorch error message back, not a generic
one, and nothing is left half-created. This means, for PyTorch
specifically, `code` must be the *exact* architecture that produced the
uploaded weights - `load_state_dict()` fails on any mismatch (missing/
extra/wrong-shape params), unlike TensorFlow's H5 format, which bakes in
both architecture and weights, so the model's `code` field isn't even
read at real-time-inference time (confirmed via `model_inference/
tensorflow/inference.py`, which just does `keras.models.load_model()` on
the downloaded file directly).

Verified for real, not just via the pytest suite below: built and
deployed the real `backend`/`tfexecutor`/`pthexecutor` images, imported
a real (untrained-but-real) `.h5` and a real `.pth` against the live
cluster, confirmed both landed as `status="finished"` results with the
uploaded bytes on disk, confirmed the TF import could actually be
deployed for real-time inference and produce a real prediction from a
real running pod, and confirmed a garbage upload is rejected with the
real underlying error (`Unable to synchronously open file (file
signature not found)`).

`uv run pytest tests/test_deployments.py -k import` (6 new tests,
40/40 total) - mocks `httpx.AsyncClient.post` (the one genuinely
external call, to the executor's `/validate_model/`), not the executor
service itself.

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
10. **`app/blockchain.py` crashed the *entire app's* Litestar lifespan on
    startup whenever `ENABLE_FEDML_BLOCKCHAIN=1`** - `from web3 import
    Web3` pulls in `eth_abi` → `parsimonious`, which does `from inspect
    import getargspec`, removed in Python 3.11. Same root cause already
    shimmed in `model_training/tensorflow/blockchainSingleFederatedTraining.py`,
    just never applied here. Found by actually booting this backend with
    the feature enabled against a real Ethereum devnet, not by reading
    the diff between Python versions - fixed with the identical
    `inspect.getargspec = inspect.getfullargspec` shim, added before the
    `web3` import. **Superseded 2026-08-05**: `web3` bumped 5.28.0 ->
    7.16.0 (see item 12 below) dropped this whole dependency chain -
    `eth_abi` no longer pins an old `parsimonious`, and modern
    `parsimonious` doesn't touch `inspect.getargspec` at all. The shim
    was removed from both this file and the model_training copy; kept
    this paragraph as the historical record of why it existed.
11. **`py-solc-x==2.0.2` hardcodes the now-dead `solc-bin.ethereum.org`
    download host** (DNS doesn't resolve at all - confirmed empirically,
    not a transient outage; the library moved to
    `binaries.soliditylang.org` in `2.0.5`). Even after bumping the pin,
    the downloaded **amd64** solc binary (solcx never ships any other
    architecture) didn't run under Docker Desktop's Rosetta emulation on
    an Apple Silicon host at all (`rosetta error: failed to open elf at
    /lib64/ld-linux-x86-64.so.2`). Rather than keep chasing a runtime
    solc dependency, `app/blockchain.py` was rewritten to load a
    **precompiled** artifact (`app/contracts/Token.json`, produced once
    via Foundry's `forge build` - genuinely multi-arch, ran natively on
    the arm64 host) instead of calling `solcx.install_solc()`/
    `compile_standard()` on every backend startup. This also required a
    small contract change: the original `Token.sol` baked `token_name`/
    `token_symbol` into the Solidity *source* via an f-string (so it
    could never be precompiled - the source differed per deployment);
    the base `ERC20.sol` already has a `constructor(string memory name_,
    string memory symbol_)`, so the new `app/contracts/token/ERC20/Token.sol`
    just forwards to it, and `token_name`/`token_symbol` are passed as
    real constructor *arguments* at deploy time instead - one contract,
    compiled once, deployed with different args, the same pattern any
    real deployment tool (Truffle/Hardhat/Foundry) uses. `py-solc-x` is
    no longer a dependency of this project at all as a result (removed
    from `pyproject.toml`, along with `model_training/tensorflow`'s and
    `federated-module/federated_model_training/tensorflow`'s copies of
    the same pin - see `model_training/tensorflow/CLAUDE.md`'s CASE 6-9
    section for the equivalent `FederatedLearning.sol` fix and the local
    Anvil devnet this was verified against).
12. **`web3` bumped `5.28.0` -> `7.16.0`** (2026-08-05, FUTURE.md Medium
    item 5 - 3 majors behind, flagged as the single highest-value
    dependency upgrade in the whole repo). This dropped the entire
    `setuptools<81`/`protobuf==7.35.1` override/`prerelease = "allow"`/
    `pytest_ethereum`-autoload workaround chain across all three services
    that depend on `web3` (this one, `model_training/tensorflow`,
    `federated-module/federated_model_training/tensorflow`) - confirmed
    empirically (`uv lock`/`uv sync`/`uv run pytest`, not assumed from a
    changelog) that a plain `uv lock` resolves protobuf to the same
    `7.35.1` `tensorflow==2.21.0` already needs, with zero override
    needed anywhere. **v6 renamed nearly every camelCase Eth JSON-RPC
    method to snake_case** (`toChecksumAddress` ->
    `to_checksum_address`, `getTransactionCount` ->
    `get_transaction_count`, `defaultAccount` -> `default_account`,
    `Web3.toWei` -> `Web3.to_wei`, `buildTransaction` ->
    `build_transaction`, `signTransaction` -> `sign_transaction`,
    `sendRawTransaction` -> `send_raw_transaction`,
    `waitForTransactionReceipt` -> `wait_for_transaction_receipt`,
    `SignedTransaction.rawTransaction` -> `.raw_transaction`) - updated
    in `app/blockchain.py`. **`TxReceipt.contractAddress` is deliberately
    left camelCase** - unlike the methods above, this is a raw pass-
    through of the actual Ethereum JSON-RPC response field name, not a
    web3.py Python API convention, and was never renamed by any web3.py
    version (confirmed via `typing.get_type_hints(TxReceipt)` on the
    installed 7.16.0 package, not assumed). Contract *ABI* function
    names (`contract.functions.saveTrainingSettings(...)` etc., in
    `model_training/tensorflow/blockchainSingleFederatedTraining.py` and
    `federated-module`'s copy) are likewise unaffected - those are
    Solidity function names from the deployed contract itself. Verified
    for real: a full CASE=9 MNIST run (5 real on-chain federated rounds,
    real ERC20 token deployment via this file, real
    `FederatedLearning.sol` contract deployment/coordination, real
    reward transfer) against the local Anvil devnet, reaching
    `accuracy: 1.0` with zero duplicate Jobs - see
    `model_training/tensorflow/CLAUDE.md`'s CASE 6-9 section.

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
