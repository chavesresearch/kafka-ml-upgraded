# model_training-upgraded/tensorflow — status and continuation notes

**Status: CASE 1-5 fully verified end-to-end against the live local
cluster; CASE 6-8 (federated incremental/distributed) fixed by code-level
analogy to CASE 5 but not separately end-to-end verified; CASE=9
(blockchain) verified at import/compile level only, by design.**
Originally written mid-session as a token-budget checkpoint before the
CASE 1/2/3/4 retests were finished - kept up to date since as each mode
was confirmed, so this now doubles as the definition-of-done record for
the TensorFlow port, not just a resume-point. Read this fully before
touching the code further.

## What this module is

Sibling of `../../model_training/tensorflow` (kept untouched as reference/
rollback), same pattern as `backend-litestar`/`mlcode_executor-litestar`/
`datasources-package`: a from-scratch-feeling but behaviorally faithful
port to modern TensorFlow (2.21.0) + uv, fixing only what's actually broken
by that upgrade. 9 training modes (`CASE` env var 1-9), see
`../../model_training/tensorflow/training.py` for the dispatch table -
**all 9 must keep working**, this was an explicit requirement from the user,
not a nice-to-have.

## Completed and verified so far

### Code changes (all in this directory)

1. **`kafka_dataset.py` (NEW file)** - replaces
   `tensorflow_io.kafka.KafkaDataset` (bounded offset-range replay, used by
   every non-streaming mode) and
   `tfio.experimental.streaming.KafkaBatchIODataset` (incremental/online
   modes) with `kafka-python`-based implementations. tensorflow-io hasn't
   shipped since mid-2023 and caps at TF 2.16 - same blocker that hit
   `mlcode_executor-litestar/tfexecutor` earlier. The bounded reader
   mirrors an *already-existing* in-repo pattern
   (`KafkaModelEngine.__createconsumer__`, and
   `../../model_training/pytorch/TrainingKafkaDataset.py`'s
   `__createconsumer__` - same "topic:partition:start:end" string, same
   assign+seek+read-until-end-offset approach) - not a new invention.
   `get_streaming_kafka_batches` (for incremental modes) polls a real
   consumer group and yields one small `tf.data.Dataset.from_tensor_slices`
   per poll cycle with new data; `stream_timeout=-1` means poll forever
   (indefinite training).
2. **`decoders.py`** - `AvroDecoder` switched from
   `tfio.experimental.serialization.decode_avro` to `fastavro`, wrapped in
   `tf.py_function` (fastavro isn't a native TF op, so it can't be traced
   directly inside the `.map()` calls `mainTraining.py` builds - verified
   this bridging actually works in a real traced `tf.data.Dataset.map()`
   pipeline, not assumed). `RawDecoder`'s `np.fromstring` swapped for
   `np.array(x.split(), dtype=int)` (equivalent, avoids a deprecated call).
3. **`utils.py`** - `string_to_numpy_type`'s dict fixed for numpy's removed
   `np.float`/`np.string`/`np.bool` aliases (now `np.float64`/`np.bytes_`/
   `np.bool_`). **Also**: `load_model()` now calls
   `model.compile_from_config(model.get_compile_config())` after
   `keras.models.load_model()` - **this is a real Keras 3 bug found via
   actual end-to-end training**, not a lint fix: a model reloaded from disk
   keeps a *deserialized* optimizer object with a stale binding to
   pre-save variable objects, and the first `.fit()` raises `ValueError:
   Unknown variable ... This optimizer can only be called for the
   variables it was originally built with`. Reproduced in isolation
   (compile a model, save without fitting, reload, fit -> crashes;
   apply the round-trip fix -> works) before applying it - see the
   transcript/git history for the isolated repro if this needs
   re-verifying.
4. **`mainTraining.py`** - `get_train_data`/`get_online_train_data` now call
   `kafka_dataset.py`'s two functions instead of the tfio ones (the
   `.map(lambda x, y: decoder.decode(x, y))` call sites themselves are
   **unchanged** - only the dataset *source* changed). `create_distributed_model`'s
   `metrics=` fixed from a flat list to a per-output dict (`{m.name:
   list(metrics) for m in self.tensorflow_models}`) - Keras 3 rejects the
   old flat-list form for multi-output models with `ValueError: tuple
   arity mismatch`. Verified both the compile fix and that the
   `<submodel>_<metric>` history-key convention `saveDistributedMetrics`/
   `DistributedTrackTrainingCallback` slice on still holds in Keras 3.
5. **`FederatedKafkaMLModelSink.py`** - `__parse_model_compile_args` now
   returns `model.get_compile_config()` directly (the removed
   `model._get_compile_args()` + manual per-key
   `tf.keras.optimizers.serialize()`/etc. loop is gone - `get_compile_config()`
   already returns everything pre-serialized, so the manual loop doesn't
   just need adapting, it has nothing left to do). Removed the now-dead
   `__get_metric_name` helper and the now-unused `import tensorflow as tf`.
   **Verified wire-compatible** with `../../federated-module/federated_model_training/tensorflow/KafkaModelEngine.py`'s
   `__deserialize_compile_args__` (untouched, still on its original TF
   pin) via a real round-trip test - the extra keys `get_compile_config()`
   includes (`loss_weights`, `run_eagerly`, `steps_per_execution`,
   `jit_compile`) pass through that generic-passthrough deserializer and
   into `model.compile(**compileParams)` without error. **Do not need to
   touch federated-module** because of this.
6. **`blockchainSingleFederatedTraining.py`** - added an
   `inspect.getargspec = inspect.getfullargspec` shim at the top (before
   `from web3 import Web3`). `web3==5.28.0` -> `eth_abi==2.2.0` ->
   `parsimonious==0.8.1` (pinned `<0.9.0` by eth_abi, can't just bump it)
   does `from inspect import getargspec`, removed in Python 3.11. Shim is
   safe: parsimonious only ever reads `.args` off the result, which
   `getfullargspec` still provides identically.
7. **`training.py`** - the `BlockchainSingleFederatedTraining` import moved
   from module level to *inside* the `elif case ==
   BLOCKCHAIN_FEDERATED_LEARNING:` branch (lazy). Without this, **all 9**
   modes would eagerly import the whole web3/eth_abi/parsimonious chain
   just to run e.g. plain classic training - mirrors
   `backend-litestar`'s existing `_maybe_create_blockchain_token()` lazy-import
   precedent for this exact same optional feature.

### Packaging

- `pyproject.toml`/`uv.lock` (new uv project, `requirements.txt` deleted).
  Key pins: `kafka-python==3.0.9`, `fastavro==1.12.2`, `numpy==2.4.6`
  (ceiling forced by Python 3.11, which is what `tensorflow/tensorflow:2.21.0`'s
  base image actually ships - confirmed by running it, not assumed),
  `scikit-learn==1.9.0`, `seaborn==0.13.2`, `matplotlib==3.11.1`,
  `confluent-kafka==2.15.0`, `py-solc-x==2.0.2`, `web3==5.28.0`,
  `tensorflow==2.21.0` (needed explicitly in `pyproject.toml`, unlike the
  old `requirements.txt` which relied on the base image's system TF - `uv
  sync` creates an isolated `.venv` that can't see it, same lesson already
  hit in `mlcode_executor-litestar/tfexecutor`).
  - `setuptools<81`: `web3==5.28.0` does a bare `import pkg_resources` at
    import time; setuptools removed `pkg_resources` as of 81.0.0.
    Confirmed 80.9.0 still has it, 83.0.0 doesn't, by actually installing
    both in a scratch venv.
  - `[tool.uv] override-dependencies = ["protobuf==7.35.1"]`: **hard,
    disjoint conflict** - `web3==5.28.0` pins `protobuf<4,>=3.10.0` directly
    (not transitive), `tensorflow==2.21.0` needs `protobuf>=6.31.1,<8.0.0`.
    No version satisfies both. Verified empirically (not assumed) that
    web3 5.x doesn't actually break at runtime with modern protobuf: built
    a `Web3(Web3.HTTPProvider(...))` instance and called
    `Web3.toChecksumAddress(...)` successfully with protobuf 7.35.1
    installed alongside tensorflow 2.21.0 in the same venv. Pinned to the
    exact stable release (not a range) because `prerelease = "allow"`
    (needed for `ipfshttpclient==0.8.0a2`, itself a `web3` dependency) would
    otherwise happily resolve protobuf to an rc.
- `Dockerfile`/`start.sh`: uv-based pattern matching the other services
  (`uv sync --locked --no-install-project` then `uv sync --locked` in
  separate layers, `CMD ["./start.sh"]` -> `uv run training.py`). `TFTAG`
  bumped `2.7.0` -> `2.21.0`.
- `.gitignore`/`.dockerignore` added (`.venv/`, `__pycache__/`, `*.h5`,
  `confusion_matrix.png`).
- Docker image builds clean: `kafka-ml-model-training-tensorflow:test`.

### Verification done

- **Import-level**: all 9 `CASE` classes + both orchestrators
  (`training.py` as a whole) import cleanly, both in a local `uv run
  --with tensorflow==2.21.0` venv and inside the actual built container.
  The lazy blockchain path (`from blockchainSingleFederatedTraining import
  BlockchainSingleFederatedTraining`) also imports cleanly on its own
  (confirms the `getargspec` shim works).
- **Real end-to-end, CASE=1 (SingleClassicTraining), against the live
  local cluster** (Docker Desktop Kubernetes, namespace `kafkaml` - see
  "Test infrastructure" below): seeded a real `Configuration`/`MLModel`
  (framework=`tf`, a real 2-layer Keras `Sequential` as `code`)/
  `Deployment`/`TrainingResult` chain directly in `backend-litestar`'s
  sqlite DB; sent 40 real RAW-format messages via `datasources-package`'s
  `RawSink`; ran the actual trainer image as a pod with real env vars
  (`CASE=1`, `RESULT_URL=http://backend:8000/results/1`, etc.). Confirmed,
  in order: pre-model download via `backend -> tfexecutor` real HTTP
  round-trip; Kafka control-topic consumption with correct
  deployment-id filtering (a stale message from an earlier test, key=42,
  was correctly ignored; the real one, key=1/43 depending on run, was
  picked up); `get_bounded_kafka_dataset` correctly replaying the exact
  40-message range with the right train/val/test split arithmetic
  (28/8/4, matching validation_rate=0.2/test_rate=0.1); a real `.fit()`
  call actually executing (after the Keras 3 `load_model` fix above);
  per-epoch metrics POSTed to the backend; final trained model + metrics
  uploaded, with real accuracy/loss numbers landing in
  `GET /results/`.

### A real bug found in `backend-litestar` (from the *earlier* session), via this test

This is exactly why the user wanted genuine end-to-end runs instead of
import checks. `POST /results/{id}` and `POST /results_metrics/{id}` had
no explicit `status_code`, so Litestar's POST default (201) applied - but
the Django reference explicitly returns 200 for both, and
`model_training`'s client code (`mainTraining.py`'s `sendSingleMetrics`/
`sendDistributedMetrics`, `callbacks.py`'s `__send_data` in both
callbacks, `sendTempMetrics`/`sendDistributedTempMetrics`) hardcodes `if
r.status_code == 200`. Result: every single metrics/result POST looked
like a failure to the trainer, which retried forever (`RETRIES=10` with a
5s sleep, in a loop, indefinitely, since `sendSingleMetrics`'s caller
loops again if it returns `False`) - the pod kept running, keeps
re-sending the same final result, never terminates. **This is a live
service-availability bug, not a cosmetic one.**

Fixed in `../../backend-litestar/app/controllers/`:
- `training_results.py`: `status_code=200` added to `upload_result` and
  `upload_epoch_metrics` (the two `model_training` actually depends on -
  not negotiable, verified via the Django reference which explicitly sets
  `HTTP_200_OK` there).
- Audited every other `@post`/`@put`/`@delete` in the same codebase for
  the same class of bug (Litestar defaults: GET=200, POST=201, PUT=200,
  PATCH=200, DELETE=204 - confirmed via
  `litestar.handlers.http_handlers._utils.get_default_status_code`, not
  assumed):
  - `inferences.py`'s `stop_inference` (POST /inferences/{id}): Django
    returns 200 (action on existing resource, not creation) -> fixed to
    `status_code=200`.
  - `iot_devices.py`'s `deploy_to_iot_devices` (POST
    /results/inference-iot/{id}): Django returns 200, no new resource ->
    fixed to `status_code=200`.
  - `inferences.py`'s `deploy_inference` (POST /results/inference/{id}):
    **deliberately left at Litestar's default 201**, on the user's
    explicit call after checking - this one actually creates a new
    `Inference` DB row (`db_session.add(inference)`), so 201 is the more
    correct REST semantics for it, and neither frontend
    (`frontend`/`frontend-vue`) checks for an exact status code (both
    just test 2xx-ness) - so nothing depends on matching Django's 200
    here. Don't "fix" this one back to 200.
  - `datasources.py`, `configurations.py`, `models.py`,
    `create_iot_device`: already matched (Django 201 == Litestar default
    201) - no changes needed.
  - All `@delete` handlers already had explicit `status_code=200` from
    the *original* backend-litestar port session - correctly done then,
    nothing to fix now.

## CASE=1 retest - CONFIRMED PASSED

Re-ran CASE=1 after rebuilding `backend-litestar` with the status-code fix
(fresh DB rows `model_id=1`/`deployment_id=1`/`result_id=1`, fresh
`RawSink` data on `e2e-training-data-2`). The pod reached `Succeeded`
cleanly, logs showed exactly one "Sending result data to backend" /
"Result data sent correctly to backend!!" pair (no retry loop), and
`GET /results/` showed `status: "finished"`. The retry loop is confirmed
fixed, not just "metrics eventually landed anyway".

## CASE=3 (DistributedClassicTraining) - CONFIRMED PASSED, found 2 more real bugs

Seeded a real 2-submodel distributed chain (`e2e-cloud-model` id=2,
father_id=None; `e2e-edge-model` id=3, father_id=2 - see "Test
infrastructure" below for the exact DB-schema father/child direction,
it's counter-intuitive) and ran it for real. Two more genuine Keras-3
regressions surfaced, both now fixed in `mainTraining.py`:

1. **`format_ml_code` in `mlcode_executor-litestar/tfexecutor/app.py`
   requires distributed submodel `code` to end with a bare expression, no
   trailing `model = ` and no trailing newline** - it does
   `code[:code.rfind('\n')+1] + 'model = ' + code[code.rfind('\n')+1:]`,
   which silently mis-fires if the code already ends in `model = ...\n`
   (produces a dangling `model = ` on its own line -> `SyntaxError`). Not
   a bug fixed in code - a **usage/authoring constraint** to remember when
   writing any more test distributed model code: last line must be a bare
   `tf.keras.Model(...)` expression, string must not end in `\n`.
2. **Real bug, fixed**: `train_classic_model` and `test_model` in
   `mainTraining.py` called `self.model.fit(...)`/`self.model.evaluate(...)`
   directly on the raw Kafka `tf.data.Dataset` (single `y` per batch), but
   a distributed model has `N` outputs (one per submodel in the chain, all
   supervised by the same label). Keras 2 silently broadcast one `y`
   tensor across every output; Keras 3 hard-errors with `ValueError: y_true
   and y_pred have different structures`. The sibling semi-supervised
   methods (`train_classic_semi_supervised_model`,
   `train_incremental_semi_supervised_model`) already had a `hasattr(self,
   'N')` branch that replicates `y` into an `N`-length list/tuple for
   exactly this reason - `train_classic_model`/`test_model` (and
   `train_incremental_model`, same pattern, fixed for CASE=4) just never
   got the same treatment. Confirmed byte-identical to the original
   `model_training/tensorflow/mainTraining.py` before this fix - this is a
   **latent bug that predates the port**, only surfaced now because Keras
   3 stopped tolerating the structure mismatch. Fix: `.map(lambda x, y:
   (x, tuple(y for _ in range(self.N))))` on `train_dataset`/
   `validation_dataset`/`test_dataset` whenever `hasattr(self, 'N')`,
   right before the `.fit()`/`.evaluate()` call.

Also reconfirmed (again, don't fix - out of scope, pre-existing,
byte-identical to original): `DistributedClassicTraining.test()`'s
metric-zip-by-position produced another suspiciously-round `test_metrics`
value in the real run, same family as the `SingleClassicTraining.test()`
oddity noted below.

Final result: both submodels (`result_id=2` and `3`) reached `status:
"finished"` with real per-submodel metrics
(`cloud_model_accuracy`/`edge_model_loss`/etc. - confirms the earlier
per-output metrics-dict fix works under real training too, not just at
compile time).

## CASE=2 (SingleIncrementalTraining) - CONFIRMED PASSED, no code changes needed

This was flagged as the riskiest untested path (`get_streaming_kafka_batches`
had no directly-comparable in-repo precedent). Ran for real: seeded a
single non-distributed model (`e2e-incremental-model`, id=4,
`deployment_id=3`, `incremental=True`), started the trainer pod, then used
`datasources-package`'s `OnlineRawSink` to send two separate 10-message
bursts (~10s apart) to a fresh topic (`e2e-incremental-data`). Confirmed
in the logs: the streaming consumer picked up **exactly two** separate
poll cycles ("Received 10 new message(s)..." logged twice, with a real
`.fit()` call after each), then correctly timed out and stopped after
`STREAM_TIMEOUT=20000`ms of no further data, matching
`get_streaming_kafka_batches`'s designed "yield one mini-batch per poll
cycle, `return` after `stream_timeout` ms of silence" behavior exactly.
Pod reached `Succeeded`, result reached `status: "finished"`. **No fix
needed here** - the streaming implementation written earlier this session
worked correctly the first time once the DB/control-message setup was
right.

Gotcha worth keeping for next time: `OnlineRawSink`'s default `.send()`
auto-infers `data_type`/`label_type`/reshape from the *first* value passed
and fires the online control message as a side effect of that first call -
for deterministic test timing (the streaming consumer's group uses
`auto_offset_reset='latest'` with no persisted offset, so data produced
*before* the consumer joins is silently skipped), it's more reliable to
pre-set `sink.data_type`/`label_type`/`data_reshape`/`label_reshape`/
`input_config`/`_configured_format=True` by hand and call the public
`sink.send_online_control_msg()` directly, sleep a few seconds so the
trainer's consumer has time to actually join the group and start polling,
*then* send the real data bursts.

## CASE=4 (DistributedIncrementalTraining) - CONFIRMED PASSED

Combined both setups above: 2 fresh distributed submodels (`e2e-cloud-model-2`
id=5, `e2e-edge-model-2` id=6, `deployment_id=4`) plus the same
two-burst `OnlineRawSink` pattern against a fresh topic
(`e2e-distributed-incremental-data`). This is the one path where
`get_streaming_kafka_batches`'s defensive `str(group_id)` coercion
actually gets exercised with a non-string `group_id` - confirmed in the
logs: `group=[5, 6]` (the Python list, stringified to `"[5, 6]"` for
Kafka's wire protocol) worked correctly as a real consumer group id, both
bursts were received, both submodels trained together (using the CASE=3
y-replication fix), and both results (`result_id=5` and `6`) reached
`status: "finished"`. No new bugs found here - this case just validates
the CASE=2 and CASE=3 fixes compose correctly.

## CASE=5 (SingleFederatedTraining) - CONFIRMED PASSED, real multi-service round

Once `federated-module-upgraded` was ported (see its own `CLAUDE.md`),
CASE=5 was run as a **real, complete, multi-service end-to-end federated
round** - not mocked, not import-only. Full cast: this trainer
(`EdgeBasedTraining(SingleFederatedTraining())`), `federated_model_control_logger`,
`federated_data_control_logger`, `federated_backend` (Django, real
Kubernetes Job creation), and a real `federated_model_training/tensorflow`
edge worker Job. Sequence, all real:

1. This pod downloaded the pre-model, sent it (4 layer-weight messages +
   control message, `version=-1` since `AGGREGATION_ROUNDS=1` made this
   the only/last round) to `FED-{federated_string_id}-model_data_topic`/
   `model_control_topic` via `FederatedKafkaMLModelSink`.
2. `generate_and_send_data_standardization()` published to
   `MODEL_LOGGER_TOPIC` (`FEDERATED_MODEL_CONTROL_TOPIC`);
   `federated_model_control_logger` relayed it to `federated_backend`,
   registering a `ModelSource` row.
3. A real datasource was sent via `datasources-package`'s
   `FederatedRawSink` (40 RAW messages); `federated_data_control_logger`
   relayed the registration to `federated_backend`, registering a
   `Datasource` row.
4. `federated_backend`'s collision check matched the two (real bug found
   and fixed here - see `federated-module-upgraded/CLAUDE.md` - a blank
   Kubernetes `Configuration()` was discarding the in-cluster default,
   `LocationValueError: No host specified` on every attempt) and created
   a **real** `batch/v1 Job` via the real Kubernetes API.
5. That Job ran `federated_model_training/tensorflow`, which downloaded
   the model via `KafkaModelEngine` (`model_from_json`/`set_weights` -
   the Keras-3 JSON-architecture round-trip verified here for the first
   time under real training, not just an isolated probe), replayed the 40
   messages via the shared `kafka_dataset.py`, trained one local epoch,
   and sent results back via `FederatedKafkaMLAggregationSink`.
6. This trainer received the edge's weights via
   `KafkaModelEngine.setWeights`, ran `aggregate_model()`'s `FedAvg` path,
   and - since this was the last round - sent the final model and real
   metrics (`accuracy: 0.375, loss: 0.71...`) to `backend-litestar`.

Both the main trainer pod and the edge worker Job reached `Completed`
cleanly; `GET /results/{id}` showed `status: "finished"` with the real
metrics above. **No code bugs found on this trainer's own side** during
this run - `FederatedKafkaMLModelSink`, `KafkaModelEngine.setWeights`, and
`aggregate_model`'s `FedAvg` logic all worked correctly as already-shipped
code (the JSON-architecture round-trip in particular was a real Keras-3
risk that turned out fine, not assumed).

## Remaining work, in priority order

1. **CASE 6-8 (federated incremental/distributed variants) and CASE=9
   (blockchain)** - CASE 6-8 got the same code-level fixes as CASE 5 (the
   y_true/y_pred structure fix in particular - see
   `federated-module-upgraded/CLAUDE.md`) but were **not** separately
   run end-to-end - that would need either a distributed-and-federated
   scenario (2+ real edge devices each training a different submodel) or
   a real streaming datasource feeding an incremental federated round,
   neither attempted given time. CASE=9 additionally needs a real or
   local-testnet Ethereum node - still import/compile-level only, by
   design, not oversight. State this plainly if asked. Worth a quick look
   at `edgeBasedTraining.py`'s own training loop for the same y_true/y_pred
   structure class of bug found in CASE=3/4 (not yet checked - it doesn't
   call `train_classic_model`/`train_incremental_model` directly, so it
   may or may not share the bug).
2. **Write `../CLAUDE.md`** (one level up, `model_training-upgraded/`
   root) - hasn't been created yet. Should summarize this file's contents
   at a higher level once TensorFlow is fully done, the way
   `datasources-package/CLAUDE.md` etc. do, plus set up for the PyTorch
   section once that's ported.
3. **Write `README.md`** for this directory (hasn't been created/updated
   from the original yet - the copied one still describes the old
   Flask-era... actually the old one never mentioned Flask, but it still
   references `requirements.txt` and doesn't mention any of the above).
4. **PyTorch port** (`../../model_training/pytorch`) - explicitly deferred
   to a separate pass (user's own decision: "TensorFlow first, PyTorch
   after"). Nothing done yet. Known issues already spotted during the
   initial scan, for whenever that pass starts:
   - `avro.schema`/`avro.io` (`DatumReader`/`BinaryDecoder`) in
     `TrainingKafkaDataset.py` - same dead-`avro-python3`-adjacent
     situation as everywhere else; should switch to `fastavro` to match
     `mlcode_executor-litestar`/`datasources-package`'s precedent.
   - `DatumReader(data_scheme)` is called with a raw string instead of a
     parsed schema in `TrainingKafkaDataset.py` - already broken today,
     independent of any upgrade (same class of latent bug as the
     `JsonDecoder` arity mismatch documented in
     `mlcode_executor-litestar/CLAUDE.md` - flag, don't silently fix
     unless asked, it's outside a "fix what the upgrade broke" scope).
   - `np.fromstring` (deprecated, not removed - lower priority than the
     TF side's now-removed `np.float`/etc.).
   - `ignite.contrib.handlers.TensorboardLogger` - **already confirmed
     still works** in `pytorch-ignite==0.5.5` (tested directly in
     `mlcode_executor-litestar/pthexecutor`'s venv already, during that
     port) - probably fine as-is, low risk.
   - Should reuse `pthexecutor`'s already-settled pins for consistency:
     `torch==2.13.0+cpu`, `torchvision==0.28.0+cpu`,
     `pytorch-ignite==0.5.5`, same `[tool.uv.sources]`/explicit-index
     pattern for the CPU wheel.
   - Needs the same uv conversion + Dockerfile bump (currently
     `BASEIMG=python:3.8.6`, EOL).
5. **Confirmed but deliberately not fixed (out of scope)**:
   `SingleClassicTraining.test()` and `DistributedClassicTraining.test()`
   both zip `epoch_training_metrics.keys()` against `evaluate()`'s
   returned list *by position*, and both real CASE=1 and CASE=3 test runs
   produced suspiciously-round `test_metrics` values (e.g. `{"loss":
   [0.5]}`), consistent with `evaluate()`'s actual return order being
   `[loss, accuracy, ...]` while `epoch_training_metrics`'s dict key order
   is `[accuracy, loss, ...]` - i.e. the values are very likely being
   assigned to the wrong metric names. Confirmed byte-identical to the
   original in both files - a **pre-existing bug that predates this
   upgrade entirely**, not something the TF/Keras 3 port broke. Left
   alone per the user's "faithful 1:1, fix only what's broken by the
   upgrade" scoping decision. Flag if asked, don't silently fix.
6. Test artifacts already cleaned up (trainer pods deleted, `.e2e-scratch/`
   removed). Leftover Kafka topics (`e2e-training-data`,
   `e2e-training-data-2`, `e2e-incremental-data`,
   `e2e-distributed-incremental-data`) and DB rows in the backend's sqlite
   were left as-is - harmless on this disposable local dev cluster, and
   the DB resets on the backend pod's next restart anyway (no PVC).

## Test infrastructure (for resuming without re-deriving)

- Local cluster is **Docker Desktop's built-in Kubernetes** (`kubectl
  config current-context` -> `docker-desktop`), **not minikube** (not
  installed on this machine, despite earlier user phrasing assuming it).
  Shares the local Docker image cache directly - no `minikube image load`
  or registry push needed, just `docker build -t <name>:test .` and the
  cluster can already see it.
- Namespace: `kafkaml`.
- Currently running pods (as of this checkpoint): `kafka`, `backend`,
  `kafka-control-logger`, `tfexecutor`, `pthexecutor` all healthy.
  `frontend` is `ImagePullBackOff` - pre-existing, unrelated to any of
  this work (old published image reference, frontend hasn't been touched
  this project).
- Kafka broker: `apache/kafka:4.3.1`, KRaft mode, single node.
  `kustomize/local/resources/kafka-deployment.yaml` already sets
  `KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1` etc. - **without these, a
  single-broker cluster's `__consumer_offsets` topic can't be created
  (needs 3 brokers by default) and every consumer-group join hangs
  forever with no error at all** - this bit us once already this session,
  already fixed at the kustomize level, shouldn't recur.
- Local image tags already built and reusable: `kafka-ml-backend-litestar:test`,
  `kafka-ml-tfexecutor:test`, `kafka-ml-pthexecutor:test`,
  `kafka-ml-control-logger:test`, `kafka-ml-model-training-tensorflow:test`.
- **Seeding the backend DB** (no PVC - resets to empty on every pod
  restart!): `kubectl exec` into the backend pod, `uv run python3 -c
  "..."` with an `async with Session() as session: async with
  session.begin(): ...` block. **Gotcha**: construct
  `Configuration(name=..., ml_models=[model])` with the relationship set
  *at construction time* - touching `config.ml_models.append(...)` after
  an `await session.flush()` triggers `sqlalchemy.exc.MissingGreenlet`
  (lazy-load attempted outside an awaited context). See this session's
  transcript for the exact working script (search for "SEEDED:" in the
  output it prints).
- **Sending test training data**: `kubectl run` a `python:3.12-slim` pod
  with a `hostPath` volume mounting `datasources-package`'s directory
  straight in (`/Users/chaves/Desktop/UpgradeKafkaML/kafka-ml-upgraded/datasources-package`
  -> `/pkg`), then `pip install -q /pkg numpy` and use `RawSink` directly
  from `kafkaml_datasources`.
- **Trainer test pod**: a plain `Pod` manifest (not a `Job` - was easier to
  inspect/delete/recreate quickly), image
  `kafka-ml-model-training-tensorflow:test`, `imagePullPolicy: IfNotPresent`.
  Template lives at `/tmp/trainer-pod.yaml` (scratch, not committed - recreate
  from this file's env var list if it's gone: `CASE`, `BOOTSTRAP_SERVERS=kafka:9092`,
  `RESULT_URL=http://backend:8000/results/<id>`, `RESULT_ID`, `CONTROL_TOPIC=KAFKA_ML_CONTROL_TOPIC`,
  `DEPLOYMENT_ID`, `BATCH`, `KWARGS_FIT`, `KWARGS_VAL`, `CONF_MAT_CONFIG`, `UNSUPERVISED`,
  plus for distributed modes: `OPTIMIZER`, `LEARNING_RATE`, `LOSS`, `METRICS`;
  for incremental modes: `STREAM_TIMEOUT`, `MONITORING_METRIC`, `CHANGE`, `IMPROVEMENT`;
  for federated modes: `MODEL_LOGGER_TOPIC`, `FEDERATED_STRING_ID`, `AGGREGATION_ROUNDS`,
  `DATA_RESTRICTION`, `MIN_DATA`, `AGG_STRATEGY`).
