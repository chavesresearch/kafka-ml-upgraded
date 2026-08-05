# federated-module — instructions for AI assistants

**Status: this is the deployed federated module.** CASE 5-9 (every
federated variant, including blockchain) confirmed working with real,
complete, multi-service end-to-end rounds - main trainer, both
control-logger relays, `federated_backend` (including real Kubernetes Job
creation), and the `federated_model_training` edge worker all exercised
together for real, not mocked, against a cluster wiped and redeployed
from scratch first. Two real bugs were found and fixed getting CASE 6/8
(the incremental variants) working - see "CASE 6-9 - CONFIRMED PASSED"
below. See the bottom of the `federated_backend/` section below for the
original CASE=5 run.

A faithful port of the original `federated-module`, preserved at
`../../kafka-ml/federated-module` as historical reference. Same
faithful-port philosophy as `model_training`/`model_inference`: fix only
what each dependency upgrade actually broke - plus, in this module, two
additional bugs found via real testing that were pre-existing (not
upgrade-caused) but 100% blocked the module's core function, fixed anyway
with the reasoning documented below (and one false alarm caught and
reverted before it shipped - also documented, since the lesson is worth
keeping).

## What this module actually is (read this first, it's not obvious)

This is **not** a UI/dashboard side-concern. `federated_backend` is the
**actual orchestrator** that launches `federated_model_training` edge
worker Kubernetes Jobs. The flow:

1. The main `model_training/tensorflow` trainer, running in CASE
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
   `model_training/tensorflow`) is the one that actually
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
upstream; nothing to port. Federated CASE 5-8 in `model_training`
are TensorFlow-only for this reason - not a gap introduced by this port.

## federated_model_training/tensorflow/

Same treatment as `model_training/tensorflow`, and largely reused
its already-verified fixes directly rather than re-deriving them:

- `kafka_dataset.py` - **copied verbatim** from
  `model_training/tensorflow/kafka_dataset.py`. Replaces
  `tensorflow_io.kafka.KafkaDataset`/
  `tfio.experimental.streaming.KafkaBatchIODataset` in
  `federated_mainTraining.py`'s `get_kafka_dataset`/`get_online_kafka_dataset`/
  `get_unsupervised_kafka_dataset`/`get_online_unsupervised_kafka_dataset`
  (`get_bounded_kafka_dataset`/`get_streaming_kafka_batches` respectively) -
  identical topic-spec wire format, identical API, no adaptation needed.
- `decoders.py` - **copied verbatim** from
  `model_training/tensorflow/decoders.py` (the fastavro +
  `tf.py_function` `AvroDecoder`, same `decode(self, x, y)` shape).
- `utils.py`'s `string_to_numpy_type` - same `np.float`/`np.string`/
  `np.bool` removed-alias fix as every other copy of this function in the
  project.
- **Real bug, fixed**: `federated_mainTraining.py`'s `train_classic_model`
  and `train_incremental_model` had the exact same Keras 3
  y_true/y_pred-structure-mismatch bug already found and fixed in
  `model_training/tensorflow/mainTraining.py`'s CASE=3 testing -
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
  subscribe+poll+seek - see `model_training/pytorch/CLAUDE.md`'s
  writeup of that exact bug class, already avoided here) and
  `model.to_json()`/`model_from_json()`/`get_weights()`/`set_weights()`
  for model transfer - **verified this Keras-3 JSON-architecture
  round-trip works** (a real risk given Keras 3's serialization rewrite)
  with a direct `to_json()` -> `model_from_json()` -> `set_weights()`
  probe before trusting it, not assumed from reading the diff between
  Keras versions.
- `federated_blockchainSingleClassicTraining.py` - same
  `inspect.getargspec = inspect.getfullargspec` shim as
  `model_training/tensorflow/blockchainSingleFederatedTraining.py`
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
  `model_training/tensorflow` for the shared dependencies
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
   was found in `backend/app/utils.py`'s `kubernetes_api_client`**
   (same author, same copy-paste pattern, `kubernetes_asyncio` instead of
   `kubernetes` - verified the async client's `Configuration`/`ApiClient`
   have the identical behavior before fixing) - fixed there too, since an
   API-driven integration test that actually deploys a training job would
   have hit it. Pre-existing, not upgrade-caused, on both sides - fixed
   anyway because it 100% blocked real Job creation.

**Confirmed with a real, complete, multi-service end-to-end CASE=5 round**
(see `model_training/tensorflow/CLAUDE.md`'s CASE=5 section for
the full blow-by-blow): main trainer -> data standardization ->
`federated_model_control_logger` -> `federated_backend` (`ModelSource`
registered); `FederatedRawSink` -> `federated_data_control_logger` ->
`federated_backend` (`Datasource` registered, collision matched); **a real
Kubernetes Job was created via the real API** (fix #3 above verified
against the actual cluster, not mocked); the edge worker Job trained for
real and sent results back; the main trainer aggregated (FedAvg, 1 round)
and posted a real finished result (`status: "finished"`, real
accuracy/loss) back to `backend`. Every piece in this module
was exercised for real in this one run.

## CASE 6-9 - CONFIRMED PASSED, full stack re-verified from a clean wipe

Run as part of a deliberate full-matrix pass (namespace deleted and
redeployed from scratch first, then every CASE 1-9 driven for real - see
`model_training/tensorflow/CLAUDE.md`'s identically-named section for the
complete record). Every case reached a real `status: "finished"` result.
Two real bugs specific to this module were found and fixed in the
process (a third, in `mainTraining.py`, is documented on the main
trainer's side):

1. **`federated_model_training/tensorflow/Dockerfile` never got the
   non-root-user setup `model_training/tensorflow`'s own Dockerfile
   already has.** Every Job this module (or the main `backend`) creates
   is forced to `runAsUser: 1000` at the container securityContext level
   regardless of what the image itself does - without a matching
   `useradd`/`chown`, that UID has no writable `$HOME`, so `uv run`
   failed immediately with `Permission denied: /.cache/uv`. This meant
   **the edge worker could never actually start**, on any CASE. Fixed:
   added the same `useradd --create-home --uid 1000 kafkaml && chown -R
   kafkaml:kafkaml /usr/src/app` + `USER kafkaml` pattern to this
   Dockerfile.
2. **Real, pre-existing bug in `federated_backend/automl/views.py`'s
   `ModelFromControlLogger.post()`** (confirmed byte-identical in
   `../kafka-ml` - not introduced by this port, a genuine gap in the
   original upstream code). Its case-number computation only ever
   produced 1, 3, or 5 - it never consulted the `incremental` flag it had
   already destructured from the request body - and its
   datasource-matching loop's guard (`if not incremental and
   ds_serializer.data['total_msg'] is not None`) **actively skipped**
   attempting a match whenever the model was incremental. Net effect:
   a federated-incremental model (CASE 6, and by extension CASE 8) could
   register successfully but could *never* be matched with a compatible
   datasource - not a timing/race issue, a structural dispatch bug found
   only by actually running CASE=6 for real (an import/compile check
   would never catch this - both functions execute without error, they
   just silently never call `deploy_on_kubernetes()`). Fixed: the case
   computation now also branches on `incremental` (1=single, 2=single
   incremental, 3=distributed, 4=distributed incremental, 5=blockchain -
   matching `federated_model_training/tensorflow/utils.py`'s own local
   1-5 numbering, which `check_colission`'s case-based total_msg gating
   already assumed), and the loop guard now reads `if incremental or
   ds_serializer.data['total_msg'] is not None` - `check_colission`
   itself already skips the total_msg>=min_data comparison for cases 2/4,
   so nothing else needed to change.

**A resource-hygiene issue found, not fixed (flagged, out of scope for
this pass)**: neither `Datasource` nor `ModelSource` rows are ever marked
consumed or deleted after a successful match - confirmed identical in
`../kafka-ml`, a pre-existing design gap. Every new registration re-scans
and re-matches against every past registration forever. Running CASE
1-9's tests back-to-back in one session without restarting
`federated-backend` between the federated ones caused 8 duplicate edge
worker Jobs to spin up from stale earlier-test registrations, briefly
overloading the local cluster. Each case is solid in isolation (that's
what's shipped); this is a real risk for sustained federated usage,
worth fixing properly (mark-consumed or delete-after-match) as a
follow-up - see `model_training/tensorflow/CLAUDE.md`'s matching note.

**CASE=9 (blockchain) additionally required precompiling
`FederatedLearning.sol` via Foundry** instead of `blockchain_utils.py`'s
previous runtime `solcx.install_solc()`/`compile_standard()` - solcx only
ships amd64 solc binaries, which don't even run under Docker Desktop's
Rosetta emulation on an Apple Silicon host. See
`model_training/tensorflow/CLAUDE.md`'s CASE 6-9 section for the full
explanation and `kustomize/local/resources/blockchain-devnet.yaml` for
the local Anvil devnet this was verified against - real contract
deployment, real on-chain round coordination, real ERC20 reward transfer,
all exercised for real, not mocked.

## Real-MNIST multi-epoch pass (`epochs=5`/`agg_rounds=5`) - CONFIRMED PASSED, one real deadlock found+fixed

A follow-up full-matrix pass driving CASE 5-9 with real MNIST images and
`epochs=5`/`agg_rounds=5` (not tiny synthetic data at `epochs=1`) - see
`model_training/tensorflow/CLAUDE.md`'s matching section for the full
record and `integration-tests/mnist_case{5..9}_*.py` for the scripts.
Found and fixed a real deadlock in this module's own
`federated_mainTraining.py`'s `train_incremental_model` (CASE=6/8 only) -
its retry-on-empty loop re-iterated an already-exhausted one-shot Python
generator forever instead of fetching a fresh one, which silently hung a
federated-incremental round whenever its streaming consumer joined after
that round's data had already all arrived. See that fix's own inline
comment for the full diagnosis - confirmed byte-identical to
`../kafka-ml`, pre-existing, just never exercised under real (not
synthetic-instant) timing before now.

Also: `federated-module/kustomize/local` **did not exist as a committed
overlay before this pass**, despite `kustomize/README.md` listing it as
one of the available versions - the federated module had only ever been
deployed by hand-rolling a one-off `kubectl apply -k` + manual image/
imagePullPolicy patches in earlier sessions, never actually committed.
Reconstructed and committed from the live cluster's actual applied state
(`kubectl get deploy -o yaml`, diffed against `kustomize/base`'s
placeholders) - mirrors the main repo's own `kustomize/local` overlay
exactly (locally-built `:test` images, `IfNotPresent` patches, same
`kafkaml` namespace). Deploy both together:
```
kubectl apply -k kustomize/local
kubectl apply -k federated-module/kustomize/local
```

## Remaining work

1. Write/update `README.md` files (all four still describe
   `pip install -r requirements.txt`).
2. `federated_model_training/pytorch` doesn't exist upstream - out of
   scope, nothing to port.
