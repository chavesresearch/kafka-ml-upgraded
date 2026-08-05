# model_training/tensorflow — status and continuation notes

**Status: all 9 CASEs fully verified end-to-end against a real, freshly
wiped local cluster (namespace deleted and redeployed from scratch first)
- including CASE=9 (blockchain) against a real local Ethereum devnet, not
mocked or import-checked only.** CASE 6-9 were the last to be confirmed;
see "CASE 6-9 - CONFIRMED PASSED" below for the full record, including
three real bugs found and fixed in the process (two in this repo, one
pre-existing in `federated_backend`, all documented where fixed).
Originally written mid-session as a token-budget checkpoint before the
CASE 1/2/3/4 retests were finished - kept up to date since as each mode
was confirmed, so this now doubles as the definition-of-done record for
the TensorFlow port, not just a resume-point. Read this fully before
touching the code further.

## What this module is

Sibling of `../../../kafka-ml/model_training/tensorflow` (kept untouched as reference/
rollback), same pattern as `backend`/`mlcode_executor`/
`datasources`: a from-scratch-feeling but behaviorally faithful
port to modern TensorFlow (2.21.0) + uv, fixing only what's actually broken
by that upgrade. 9 training modes (`CASE` env var 1-9), see
`../../../kafka-ml/model_training/tensorflow/training.py` for the dispatch table -
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
   `mlcode_executor/tfexecutor` earlier. The bounded reader
   mirrors an *already-existing* in-repo pattern
   (`KafkaModelEngine.__createconsumer__`, and
   `../../../kafka-ml/model_training/pytorch/TrainingKafkaDataset.py`'s
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
   `getfullargspec` still provides identically. **Superseded 2026-08-05**:
   `web3` bumped to `7.16.0` (see "web3 5.28.0 -> 7.16.0" under Packaging
   below) - `eth_abi` no longer pins an old `parsimonious`, so this shim
   was removed. Kept this paragraph as the historical record.
7. **`training.py`** - the `BlockchainSingleFederatedTraining` import moved
   from module level to *inside* the `elif case ==
   BLOCKCHAIN_FEDERATED_LEARNING:` branch (lazy). Without this, **all 9**
   modes would eagerly import the whole web3/eth_abi/parsimonious chain
   just to run e.g. plain classic training - mirrors
   `backend`'s existing `_maybe_create_blockchain_token()` lazy-import
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
  hit in `mlcode_executor/tfexecutor`).
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
  - **All three of `setuptools<81`, the `protobuf` override, and
    `prerelease = "allow"` above are gone as of 2026-08-05** (kept the
    paragraphs above as historical record of why they existed). See
    "web3 5.28.0 -> 7.16.0" immediately below.

**web3 `5.28.0` -> `7.16.0` (2026-08-05, FUTURE.md Medium item 5)** - 3
majors behind, flagged as the single highest-value dependency upgrade in
the whole repo (it was the root cause of every workaround in this
section). Confirmed empirically that a plain `uv lock` now resolves
`protobuf` to the exact same `7.35.1` `tensorflow==2.21.0` already needs,
with **zero** override, and that `setuptools`/`prerelease = "allow"`
aren't needed either - `web3==7.16.0` has no `pkg_resources` import and no
`ipfshttpclient` dependency at all (confirmed via `pip index`/PyPI
metadata inspection, not assumed). Also dropped the `pytest_ethereum`
`addopts` workaround in `[tool.pytest.ini_options]` - that plugin doesn't
exist in this web3 version. **v6 renamed nearly every camelCase Eth
JSON-RPC method to snake_case** - `toChecksumAddress` ->
`to_checksum_address`, `getTransactionCount` -> `get_transaction_count`,
`defaultAccount` -> `default_account`, `Web3.toWei` -> `Web3.to_wei`,
`buildTransaction` -> `build_transaction`, `signTransaction` ->
`sign_transaction`, `sendRawTransaction` -> `send_raw_transaction`,
`waitForTransactionReceipt` -> `wait_for_transaction_receipt`,
`SignedTransaction.rawTransaction` -> `.raw_transaction` - all updated in
`blockchain_utils.py` and `blockchainSingleFederatedTraining.py`.
**`TxReceipt.contractAddress` is deliberately left camelCase** in both
files - it's a raw pass-through of the actual Ethereum JSON-RPC response
field name, not a web3.py API convention, and was never renamed by any
web3.py version (confirmed via `typing.get_type_hints(TxReceipt)` on the
installed package). Contract *ABI* function names
(`contract.functions.saveTrainingSettings(...)` etc.) are likewise
unaffected - those come from the deployed `FederatedLearning.sol`
contract, not web3.py's own API. **Verified for real**: a full CASE=9
MNIST run (5 real on-chain federated rounds, real `Web3`/contract calls
through every renamed method above, real ERC20 reward transfer) against
the local Anvil devnet, reaching `accuracy: 1.0` with zero duplicate
Jobs - see "CASE 6-9" below.
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
  `Deployment`/`TrainingResult` chain directly in `backend`'s
  sqlite DB; sent 40 real RAW-format messages via `datasources`'s
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

### A real bug found in `backend` (from the *earlier* session), via this test

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

Fixed in `../../backend/app/controllers/`:
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
    (`frontend`) checks for an exact status code (both
    just test 2xx-ness) - so nothing depends on matching Django's 200
    here. Don't "fix" this one back to 200.
  - `datasources.py`, `configurations.py`, `models.py`,
    `create_iot_device`: already matched (Django 201 == Litestar default
    201) - no changes needed.
  - All `@delete` handlers already had explicit `status_code=200` from
    the *original* backend port session - correctly done then,
    nothing to fix now.

## CASE=1 retest - CONFIRMED PASSED

Re-ran CASE=1 after rebuilding `backend` with the status-code fix
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

1. **`format_ml_code` in `mlcode_executor/tfexecutor/app.py`
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
`datasources`'s `OnlineRawSink` to send two separate 10-message
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

**Follow-up, 2026-08-05 (FUTURE.md High #7 - now done)**: the gotcha
above turned out to matter more than "worth keeping in mind" - the
committed `integration-tests/test_case2_single_incremental.py` never
actually applied it (it just did a fixed `time.sleep(15)` *before*
creating the sink, which doesn't help at all, since the control message
that tells the trainer to start joining its consumer group only fires on
the sink's own first `.send()`), and `mainTraining.py`'s
`train_incremental_model` had no retry logic at all: if the streaming
generator exhausted having received zero messages (exactly what happens
when a tight, delay-free burst loses this race), it fell straight through
to `training_results = {'model_trained': model_trained}` with
`model_trained` never bound - `UnboundLocalError`, caught by
`CloudBasedTraining`'s outer handler and silently retried as "keep
polling the control topic", leaving the `TrainingResult` stuck
`"deployed"` forever instead of crashing loudly. Same failure family as
`federated_mainTraining.py`'s CASE=6/8 deadlock (see "Real-MNIST
multi-epoch pass" below) - different manifestation (a crash instead of a
true infinite loop, since this version never had a retry `while` in the
first place), same root cause. **Fixed** the same way as the federated
version: `train_incremental_model` now wraps the per-window `for mini_ds
in kafka_dataset:` loop in a `while 'model_trained' not in locals()...`
loop, tracking `received_data`, and calls `self.get_data(self.kafka_topic,
decoder)` for a fresh generator on an empty pass instead of falling
through to the crash (`self.kafka_topic` is now stashed by
`SingleIncrementalTraining.get_data`/`DistributedIncrementalTraining.get_data`
for exactly this re-fetch). Verified two ways: (1) an adversarial repro -
send a burst immediately (guaranteed to race ahead of the consumer join),
wait past `stream_timeout` so the first generator instance fully
exhausts (the exact moment the old code would have crashed), then send a
second burst - passed, real `train_metrics` came back, proving the
retry recovered where the old code could not have. (2) The committed test
itself was fixed properly (not just given a longer guess-timeout) by
finally applying the gotcha above - pre-configure the sink's format and
call `send_online_control_msg()` explicitly before sending any real data,
so the control message is guaranteed to fire before the burst loop
starts; passed 3/3 consecutive real runs against the live cluster after
the fix (it had failed with the pre-existing timing bug on the first
real re-run this session, confirming the test fix was itself necessary,
not just theoretical).

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

Once `federated-module` was ported (see its own `CLAUDE.md`),
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
3. A real datasource was sent via `datasources`'s
   `FederatedRawSink` (40 RAW messages); `federated_data_control_logger`
   relayed the registration to `federated_backend`, registering a
   `Datasource` row.
4. `federated_backend`'s collision check matched the two (real bug found
   and fixed here - see `federated-module/CLAUDE.md` - a blank
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
   metrics (`accuracy: 0.375, loss: 0.71...`) to `backend`.

Both the main trainer pod and the edge worker Job reached `Completed`
cleanly; `GET /results/{id}` showed `status: "finished"` with the real
metrics above. **No code bugs found on this trainer's own side** during
this run - `FederatedKafkaMLModelSink`, `KafkaModelEngine.setWeights`, and
`aggregate_model`'s `FedAvg` logic all worked correctly as already-shipped
code (the JSON-architecture round-trip in particular was a real Keras-3
risk that turned out fine, not assumed).

## CASE 6-9 - CONFIRMED PASSED, full stack re-verified from a clean wipe

Run in one session as a deliberate full-matrix pass: `kubectl delete
namespace kafkaml` (wipe everything - DB, Kafka topics, all state), full
redeploy, then CASE 1-4/PyTorch/inference via the automated
`integration-tests/` suite, then CASE 5-9 manually driven the same way
(new committed tests: `integration-tests/test_case{5,6,7,8,9}_*.py`).
Every case reached a real `status: "finished"` result with real metrics.
Three real, previously-undiscovered bugs surfaced this way (none of them
Keras-version-related - all either infra or plain logic bugs that had
simply never been exercised before, since CASE 6-9 had never been run
end-to-end until this pass):

1. **`federated-module/federated_model_training/tensorflow/Dockerfile`
   never got the non-root-user setup `model_training/tensorflow`'s own
   Dockerfile already has** - every Job `job_manifest_generator.py`/
   `federated_backend` creates forces `runAsUser: 1000` at the container
   securityContext level regardless of what the image does, but this
   edge-worker image had no matching user/`$HOME`/ownership setup, so
   `uv run` failed immediately with `Permission denied: /.cache/uv`. CASE=5
   never caught this because... it did, actually, the very first time it
   was run this session - it just hadn't been re-verified since the
   hardening commit landed. Fixed: same `useradd --create-home --uid 1000
   kafkaml && chown -R kafkaml:kafkaml /usr/src/app` + `USER kafkaml`
   pattern, added to that Dockerfile. See `federated-module/CLAUDE.md`.
2. **Real, pre-existing bug in `federated_backend`'s
   `ModelFromControlLogger.post()`** (confirmed byte-identical in
   `../../../kafka-ml` - not a porting mistake): its case-number
   computation only ever produced 1/3/5 (ignoring `incremental`
   entirely), and its datasource-matching loop's guard
   (`if not incremental and total_msg is not None`) actively **skipped**
   matching whenever the model was incremental. Net effect: CASE 6 and 8
   (any federated-incremental model) could never be matched with a
   datasource at all - not a timing issue, a dispatch bug. Fixed in
   `federated-module/federated_backend/automl/views.py` - see that file's
   inline comment and `federated-module/CLAUDE.md` for the full
   before/after.
3. **Real, pre-existing bug in `mainTraining.py`'s `parse_metrics`/
   `parse_distributed_metrics`** (confirmed byte-identical in
   `../../../kafka-ml`): both unconditionally indexed
   `agg_metrics['validation'][keys]` assuming every training-side metric
   key also exists on the validation side - crashes with `KeyError` the
   first time a federated-incremental round finishes with an empty
   `validation` dict (a short streaming burst that never produced a
   held-out validation batch, completely normal for CASE 6/8's continuous
   short-burst sending pattern). Fixed with a `keys in
   agg_metrics['validation']` guard in both functions.

Also surfaced along the way, worth knowing if this gets extended further:
**CASE=9's real blockchain path required precompiling both Solidity
contracts (`contracts/FederatedLearning.json`, `../../backend/app/contracts/Token.json`)
via Foundry instead of solcx's runtime `install_solc()`/`compile_standard()`** -
`solcx` only ever ships **amd64** solc binaries (no arm64 build exists for
any release its index lists), and the downloaded amd64 binary doesn't
even run under Docker Desktop's Rosetta emulation on an Apple Silicon
host (`rosetta error: failed to open elf at /lib64/ld-linux-x86-64.so.2`) -
this trainer's own image is itself amd64-emulated (`tensorflow/tensorflow`
has no arm64 build for this TF version), so it's a second, unrelated
layer of emulation that solc's binary doesn't survive. Precompiling once
(Foundry's `forge build` is genuinely multi-arch, ran natively on the arm64
host) and loading the committed ABI+bytecode JSON at deploy time instead
sidesteps this entirely - see `blockchain_utils.py`'s updated
`create_federated_learning_smart_contract` and
`kustomize/local/resources/blockchain-devnet.yaml` (a local Anvil devnet,
standing in for "a real or local-testnet Ethereum node" - deterministic
pre-funded dev accounts, zero cost, zero external dependency). The
`FederatedLearning` contract's on-chain coordination (`saveTrainingSettings`/
`saveGlobalModel`/queue dequeue/`setTokens`) and the ERC20 reward transfer
at the end of the round were both exercised for real against this devnet,
not mocked.

## Real-MNIST multi-epoch pass (all 9 CASEs, `epochs=5`/`agg_rounds=5`) - CONFIRMED PASSED

A second full-matrix pass, after the CASE 1-9 pass above (which used tiny
synthetic scalar data and `epochs=1`): another clean `kubectl delete
namespace kafkaml` + redeploy, all locally-built images rebuilt first
(several had drifted behind their own latest source fixes - always diff
image build time against `git log -1 -- <dir>` before trusting a "already
built" image, don't assume). Every CASE 1-9 driven with **real MNIST
digit images** (not synthetic scalars) and **`tf_kwargs_fit="epochs=5"`**
(federated cases additionally `agg_rounds=5`), specifically to verify
genuine multi-epoch training - not just that one `.fit()` call succeeds.
Verification was two-layered, not just "did a result reach `finished`":
`result["train_metrics"]`'s per-metric list length (one entry per epoch/
round, see `parse_metrics`), **and** grepping each real training pod's
logs for actual `Epoch N/5` lines (Keras's own verbose fit() output) -
the second check is the one that actually proves 5 real epochs ran, since
a federated round's `train_metrics` entry is just that round's *final*
epoch value. Scripts: `integration-tests/mnist_common.py` (shared real-
MNIST loading + model code), `integration-tests/mnist_case{1..9}_*.py`,
`integration-tests/mnist_inference_common.py` (real inference deploy +
kubectl-verified pod + real held-out test image + real prediction). All
9 cases reached real multi-epoch training with sensible accuracy curves
(e.g. CASE=1 climbed 0.61→0.94 over 5 epochs on 1500 real images; CASE=9
reached 1.00 over 5 real on-chain rounds) and every deployed inference
correctly classified a real held-out MNIST test digit.

**One real, previously-undiscovered deadlock bug found and fixed** -
CASE=6/8 (federated-incremental) specific, in
`federated-module/federated_model_training/tensorflow/federated_mainTraining.py`'s
`train_incremental_model`. See that fix's own inline comment for the full
diagnosis; short version: `self.kafka_dataset` is a one-shot Python
generator (`get_streaming_kafka_batches`) that permanently exhausts after
`stream_timeout` ms of silence, but the retry-on-empty `while` loop around
it just re-iterated the same dead generator forever - a real deadlock
(no error, no timeout, no progress) whenever a round's streaming consumer
happened to join after all of that round's data was already sent. Fixed
by re-fetching a fresh generator (`self.get_data(training_settings)`) on
an empty pass instead of re-iterating the exhausted one. Confirmed
byte-identical to `../../../kafka-ml` - pre-existing, not introduced by
this port, only surfaced now because this was the first time CASE=6/8 was
driven with real (slower, network-round-trip-bound) timing instead of
near-instantaneous synthetic data.

Also worth keeping for next time: getting CASE=6/8's *test* data-sending
timing right took two wrong attempts before landing on the fix (see
`integration-tests/mnist_case6_federated_incremental.py`'s docstring for
the full account) - a fixed-window trickle starves round 2+, and a
*continuous* zero-gap trickle starves round *advancement* entirely (round
0 never sees the required silence to hand control back for the next
round's broadcast). The fix was discrete round-sized bursts with a
silence gap longer than `stream_timeout` between them - this is a general
lesson about testing/operating `agg_rounds > 1` federated-incremental
deployments, not just a one-off test-script bug.

## Remaining work, in priority order

1. **Write `../CLAUDE.md`** (one level up, `model_training/`
   root) - hasn't been created yet. Should summarize this file's contents
   at a higher level once TensorFlow is fully done, the way
   `datasources/CLAUDE.md` etc. do, plus set up for the PyTorch
   section once that's ported.
2. **Write `README.md`** for this directory (hasn't been created/updated
   from the original yet - the copied one still describes the old
   Flask-era... actually the old one never mentioned Flask, but it still
   references `requirements.txt` and doesn't mention any of the above).
3. ~~`federated_backend` never marks a `ModelSource`/`Datasource` row as
   consumed after a successful match~~ - **done** (2026-08-05, as part of
   the `federated_backend` Django->Litestar rewrite - see
   `../../federated-module/CLAUDE.md`'s "federated_backend/ ->
   Django->Litestar rewrite" section for the full record, including a
   second, more precise bug found the same day: `federated_model_control_logger.py`'s
   `auto_offset_reset='earliest'` was the actual cause of a worse
   "replay entire history on restart" variant). Kept this paragraph as
   the historical record of the resource-exhaustion incident that
   surfaced it.
4. **PyTorch port** (`../../../kafka-ml/model_training/pytorch`) - explicitly deferred
   to a separate pass (user's own decision: "TensorFlow first, PyTorch
   after"). Nothing done yet. Known issues already spotted during the
   initial scan, for whenever that pass starts:
   - `avro.schema`/`avro.io` (`DatumReader`/`BinaryDecoder`) in
     `TrainingKafkaDataset.py` - same dead-`avro-python3`-adjacent
     situation as everywhere else; should switch to `fastavro` to match
     `mlcode_executor`/`datasources`'s precedent.
   - `DatumReader(data_scheme)` is called with a raw string instead of a
     parsed schema in `TrainingKafkaDataset.py` - already broken today,
     independent of any upgrade (same class of latent bug as the
     `JsonDecoder` arity mismatch documented in
     `mlcode_executor/CLAUDE.md` - flag, don't silently fix
     unless asked, it's outside a "fix what the upgrade broke" scope).
   - `np.fromstring` (deprecated, not removed - lower priority than the
     TF side's now-removed `np.float`/etc.).
   - `ignite.contrib.handlers.TensorboardLogger` - **already confirmed
     still works** in `pytorch-ignite==0.5.5` (tested directly in
     `mlcode_executor/pthexecutor`'s venv already, during that
     port) - probably fine as-is, low risk.
   - Should reuse `pthexecutor`'s already-settled pins for consistency:
     `torch==2.13.0+cpu`, `torchvision==0.28.0+cpu`,
     `pytorch-ignite==0.5.5`, same `[tool.uv.sources]`/explicit-index
     pattern for the CPU wheel.
   - Needs the same uv conversion + Dockerfile bump (currently
     `BASEIMG=python:3.8.6`, EOL).
6. **Confirmed but deliberately not fixed (out of scope)**:
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
7. Test artifacts already cleaned up (trainer pods deleted, `.e2e-scratch/`
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
- Local image tags already built and reusable: `kafka-ml-backend:test`,
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
  with a `hostPath` volume mounting `datasources`'s directory
  straight in (`/Users/chaves/Desktop/UpgradeKafkaML/kafka-ml-upgraded/datasources`
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
