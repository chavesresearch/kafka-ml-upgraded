# federated-module-upgraded — instructions for AI assistants

**Status: functionally complete, CASE=5 (federated learning) confirmed
working with a real, complete, multi-service end-to-end round** - main
trainer, both control-logger relays, `federated_backend` (including a real
Kubernetes Job creation), and the `federated_model_training` edge worker
all exercised together for real, not mocked. See the bottom of the
`federated_backend/` section below for the full run.

Sibling of `../federated-module` (kept untouched as reference/rollback).
Same faithful-port philosophy as `model_training-upgraded`/
`model_inference-upgraded`: fix only what each dependency upgrade actually
broke - plus, in this module, two additional bugs found via real testing
that were pre-existing (not upgrade-caused) but 100% blocked the module's
core function, fixed anyway with the reasoning documented below (and one
false alarm caught and reverted before it shipped - also documented,
since the lesson is worth keeping).

## What this module actually is (read this first, it's not obvious)

This is **not** a UI/dashboard side-concern. `federated_backend` is the
**actual orchestrator** that launches `federated_model_training` edge
worker Kubernetes Jobs. The flow:

1. The main `model_training-upgraded/tensorflow` trainer, running in CASE
   5-8 (federated modes), calls `generate_and_send_data_standardization()`
   -> publishes a model-registration message to `MODEL_CONTROL_TOPIC`, and
   `KafkaMLSink`-style datasource clients publish to `DATA_CONTROL_TOPIC`.
2. `federated_model_control_logger` / `federated_data_control_logger`
   (two tiny Kafka-to-HTTP relay scripts, same shape as the main
   `kafka_control_logger`) consume those topics and POST the payloads to
   `federated_backend`'s `/model-control-logger/` and
   `/federated-datasources/` endpoints.
3. `federated_backend` persists each registration (`ModelSource`/
   `Datasource` Django models) and, on **every** new registration, checks
   *every* existing counterpart for a compatible match
   (`check_colission()` - input shape, reshape, restrictions, data volume
   all must line up). On a match, it directly calls the Kubernetes API
   (`deploy_on_kubernetes()`) to launch a `federated_model_training` Job -
   no polling, no separate scheduler.
4. That Job (`federated_model_training/tensorflow`) is the **edge client**:
   it consumes the per-round model (architecture + weights, via
   `KafkaModelEngine`, itself via `FED-{id}-model_control_topic`), trains
   locally on its own Kafka data partition, and sends results back via
   `FederatedKafkaMLAggregationSink` to `FED-{id}-agg_data_topic-{client}`
   / `FED-{id}-agg_control_topic`. The main trainer (already verified in
   `model_training-upgraded/tensorflow`) is the one that actually
   aggregates (FedAvg/etc.) and drives the next round.

`federated_model_training` itself never talks HTTP to anything (confirmed
by grep - no `requests`/`urllib` import anywhere in it) - it's purely
Kafka-driven. Only the two logger scripts and `federated_backend` talk
HTTP, and only to each other.

## Layout / status

| Path | Status |
|---|---|
| `federated_model_training/tensorflow/` | Functionally complete. See its own section below. |
| `federated_data_control_logger/` | uv conversion only - no code changes needed. |
| `federated_model_control_logger/` | uv conversion only - no code changes needed. |
| `federated_backend/` | uv conversion + Django/DRF/kubernetes-client version bump (kept Django - no framework rewrite, unlike the main backend's Litestar port, since this is a small 587-line satellite service and a full rewrite wasn't proportionate to what was asked). Two real bugs found and fixed - see below. |

**`federated_model_training/pytorch/` does not exist** - only a `.gitkeep`
in the original. PyTorch federated training was never implemented
upstream; nothing to port. Federated CASE 5-8 in `model_training-upgraded`
are TensorFlow-only for this reason - not a gap introduced by this port.

## federated_model_training/tensorflow/

Same treatment as `model_training-upgraded/tensorflow`, and largely reused
its already-verified fixes directly rather than re-deriving them:

- `kafka_dataset.py` - **copied verbatim** from
  `model_training-upgraded/tensorflow/kafka_dataset.py`. Replaces
  `tensorflow_io.kafka.KafkaDataset`/
  `tfio.experimental.streaming.KafkaBatchIODataset` in
  `federated_mainTraining.py`'s `get_kafka_dataset`/`get_online_kafka_dataset`/
  `get_unsupervised_kafka_dataset`/`get_online_unsupervised_kafka_dataset`
  (`get_bounded_kafka_dataset`/`get_streaming_kafka_batches` respectively) -
  identical topic-spec wire format, identical API, no adaptation needed.
- `decoders.py` - **copied verbatim** from
  `model_training-upgraded/tensorflow/decoders.py` (the fastavro +
  `tf.py_function` `AvroDecoder`, same `decode(self, x, y)` shape).
- `utils.py`'s `string_to_numpy_type` - same `np.float`/`np.string`/
  `np.bool` removed-alias fix as every other copy of this function in the
  project.
- **Real bug, fixed**: `federated_mainTraining.py`'s `train_classic_model`
  and `train_incremental_model` had the exact same Keras 3
  y_true/y_pred-structure-mismatch bug already found and fixed in
  `model_training-upgraded/tensorflow/mainTraining.py`'s CASE=3 testing -
  a distributed (multi-output) model's `y` must be replicated per output
  now, Keras 2 used to silently broadcast a single tensor. This file's own
  `train_classic_semi_supervised_model`/`train_incremental_semi_supervised_model`
  already had the exact `'N' in training_settings` replication branch (same
  asymmetry as the main trainer) - just never applied to the
  non-semi-supervised paths. Fixed identically, gated the same way.
  **Not separately end-to-end verified** (would need a real
  distributed+federated round with 2+ edge devices training different
  submodels - out of scope given time; fixed by direct analogy to the
  already-verified main-trainer fix, same code shape, same root cause).
- `KafkaModelEngine.py` / `FederatedKafkaMLAggregationSink.py` - **no
  changes needed**. Both already used `consumer.assign(...)` (not
  subscribe+poll+seek - see `model_training-upgraded/pytorch/CLAUDE.md`'s
  writeup of that exact bug class, already avoided here) and
  `model.to_json()`/`model_from_json()`/`get_weights()`/`set_weights()`
  for model transfer - **verified this Keras-3 JSON-architecture
  round-trip works** (a real risk given Keras 3's serialization rewrite)
  with a direct `to_json()` -> `model_from_json()` -> `set_weights()`
  probe before trusting it, not assumed from reading the diff between
  Keras versions.
- `federated_blockchainSingleClassicTraining.py` - same
  `inspect.getargspec = inspect.getfullargspec` shim as
  `model_training-upgraded/tensorflow/blockchainSingleFederatedTraining.py`
  (identical root cause: web3 -> eth_abi -> parsimonious -> Python 3.11
  removed `inspect.getargspec`). `federated_training.py`'s import of this
  class moved to lazy (inside the `CASE` branch), same reasoning as the
  main trainer's `training.py`.
- **Dropped from dependencies, confirmed unused**: `scikit-learn`,
  `seaborn`, `matplotlib` were in the original `requirements.txt` but
  never imported anywhere in this directory (grepped to confirm) - looks
  like copy-paste residue from `model_training`'s requirements.txt, which
  *does* use them for confusion matrices (this edge client has no
  equivalent feature). Dropped rather than carried forward as dead
  weight - unlike the "don't remove things that look unused" caution
  elsewhere in this project (exec-globals surfaces), these aren't even
  `import`ed once, so there's no exec-namespace argument for keeping them.
- Packaging: `pyproject.toml`/`uv.lock`, same pins as
  `model_training-upgraded/tensorflow` for the shared dependencies
  (`tensorflow==2.21.0`, `web3==5.28.0`, `setuptools<81`,
  `protobuf==7.35.1` override, `prerelease = "allow"` for `ipfshttpclient`).
  Docker base image bumped `tensorflow/tensorflow:2.7.0` -> `2.21.0`.

## federated_data_control_logger/ and federated_model_control_logger/

Pure uv conversion, `python:3.8.6` -> `python:3.12-slim`, no code changes -
both compile and import cleanly, both Docker images build. Dropped
`confluent-kafka` from `federated_model_control_logger`'s dependencies
(listed in the original `requirements.txt` but never imported - only
`kafka-python` is actually used, confirmed by grep). Both still use
`datetime.datetime.utcfromtimestamp()`, deprecated (not removed) as of
Python 3.12 - still works, only a `DeprecationWarning`; left as-is per
"fix only what's broken", not a hard break.

## federated_backend/

Kept Django (no Litestar rewrite, unlike the main `backend`) - this is a
small, 587-line satellite service with two endpoints, not the actively-used
multi-frontend API surface the main backend rewrite was justified by.
uv conversion + straight version bump: `django==3.2.13` -> `6.0.7`,
`djangorestframework==3.11.0` -> `3.17.1`, `django-cors-headers==3.2.1` ->
`4.9.0`, `django-model-utils==4.0.0` -> `5.0.0`, `kubernetes==11.0.0` ->
`36.0.3`, `gunicorn==20.0.4` -> `26.0.0`. Dropped `daphne` (listed in the
original `requirements.txt`; `start.sh`'s daphne/ASGI line was already
commented out - gunicorn/WSGI is what's actually run, nothing uses
`autoweb/asgi.py`).

One real Django-hygiene fix, and one real, genuinely blocking bug found via
actually running `manage.py check` and a full live end-to-end round
(not caught by reading the code, and in one case *actively
misdiagnosed on the first pass* - worth reading that part below, it's a
cautionary tale about trusting an ad-hoc test payload over the real wire
format):

1. **`fields.E010` on both `JSONField(default={})` declarations**
   (`ModelSource.blockchain`, `Datasource.dataset_restrictions`) - Django's
   own system check flags a *mutable* field default as shared across all
   field instances (a classic Python gotcha, not a new Django 6 behavior -
   this check has existed since Django 3.1). Fixed: `default=dict` (a
   callable, called fresh per instance) instead of `default={}`.
2. **A false alarm, caught before it shipped - worth recording so it
   doesn't get "fixed" again.** `check_colission()` does
   `json.loads(datasource_item['dataset_restrictions']) ==
   json.loads(model_item['data_restriction'])`. A first-pass smoke test
   POSTed a raw Python dict (`{}`) for both fields directly via Django's
   test client, which crashed with `TypeError: ... not dict` - since
   Django `JSONField` + DRF `ModelSerializer.data` preserve whatever type
   you assign, and a dict input comes back as a dict, `json.loads()`-ing
   it fails. This looked like a slam-dunk "always-broken" bug and was
   fixed by deleting the `json.loads()` calls - **but that was wrong**.
   The **real** clients (`FederatedRawSink`'s `dataset_restrictions='{}'`
   default, and the main trainer's `DATA_RESTRICTION` env var - env vars
   are always strings) both send this field as a **JSON-encoded string**,
   not a native dict - confirmed by checking what a real end-to-end run
   actually put on the wire (`'data_restriction': '{}'`, a `str`, in the
   real logs). Against *that* real input, the original `json.loads()`
   comparison is correct (and more robust than direct string equality -
   it treats semantically-equal-but-differently-formatted JSON, e.g. key
   order, as equal, which a same-instance-key-inserted-in-different-order
   pair legitimately could be for a non-empty restriction dict). **The
   `json.loads()` calls were reverted to the original.** Lesson: an
   ad-hoc test payload that doesn't match how the real client actually
   constructs a field is not evidence of a bug - verify against the real
   wire format (here: run the actual `FederatedRawSink`/main-trainer code
   path) before trusting a crash.
3. **Real bug, fixed - `kubernetes_config()` built a blank
   `client.Configuration()` and handed it to `ApiClient`, discarding
   whatever `config.load_incluster_config()` had set up as the
   process-wide default.** `Configuration.__init__` hardcodes
   `self._base_path = "http://localhost"` whenever no `host` kwarg is
   given - it does **not** consult the in-cluster default at all
   (confirmed by reading `Configuration.__init__`'s actual source, not
   assumed). So every in-cluster call (the normal case - no
   `KUBE_TOKEN`/`KUBE_HOST` override) failed with `LocationValueError: No
   host specified` the instant `deploy_on_kubernetes()` tried to create a
   real Job - **this service could never have deployed a single edge
   worker, on any `kubernetes` client version.** Fix: when no
   token/external_host override is given, call `client.ApiClient()` with
   **no** Configuration argument at all - `ApiClient.__init__` does `if
   configuration is None: configuration = Configuration.get_default_copy()`
   internally, which *does* pick up the in-cluster default (also
   confirmed by reading the source). **The exact same bug, byte-for-byte,
   was found in `backend-litestar/app/utils.py`'s `kubernetes_api_client`**
   (same author, same copy-paste pattern, `kubernetes_asyncio` instead of
   `kubernetes` - verified the async client's `Configuration`/`ApiClient`
   have the identical behavior before fixing) - fixed there too, since an
   API-driven integration test that actually deploys a training job would
   have hit it. Pre-existing, not upgrade-caused, on both sides - fixed
   anyway because it 100% blocked real Job creation.

**Confirmed with a real, complete, multi-service end-to-end CASE=5 round**
(see `model_training-upgraded/tensorflow/CLAUDE.md`'s CASE=5 section for
the full blow-by-blow): main trainer -> data standardization ->
`federated_model_control_logger` -> `federated_backend` (`ModelSource`
registered); `FederatedRawSink` -> `federated_data_control_logger` ->
`federated_backend` (`Datasource` registered, collision matched); **a real
Kubernetes Job was created via the real API** (fix #3 above verified
against the actual cluster, not mocked); the edge worker Job trained for
real and sent results back; the main trainer aggregated (FedAvg, 1 round)
and posted a real finished result (`status: "finished"`, real
accuracy/loss) back to `backend-litestar`. Every piece in this module
was exercised for real in this one run.

## Remaining work

1. Write/update `README.md` files (all four still describe
   `pip install -r requirements.txt`).
2. `federated_model_training/pytorch` doesn't exist upstream - out of
   scope, nothing to port.
3. CASE 6/7/8 (federated incremental/distributed/distributed-incremental)
   and CASE=9 (blockchain) - same scoping as the main trainer: fixed by
   code-level analogy, not separately end-to-end verified (would need
   multiple real edge devices and, for CASE=9, a real or local-testnet
   Ethereum node).
