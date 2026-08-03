# model_training-upgraded/pytorch — status and continuation notes

**Status: fully verified end-to-end.** Unlike the TensorFlow trainer,
PyTorch's `model_training/pytorch` has **no `CASE` dispatch at all** - it
only ever runs one training mode (single, non-distributed, non-incremental,
non-federated classic training). There is exactly one reachable path here,
and it's now confirmed working against the live local cluster.

## What this module is

Sibling of `../../model_training/pytorch` (kept untouched as reference/
rollback), same pattern as `tensorflow/` in this same directory,
`backend-litestar`, `mlcode_executor-litestar/pthexecutor`: a behaviorally
faithful port to modern PyTorch/ignite + uv, fixing only what's actually
broken - not a rewrite. Much smaller scope than the TensorFlow side: 4
Python files total (`training.py`, `TrainingKafkaDataset.py`, `utils.py`,
`config.py`), no per-mode class hierarchy.

## Completed and verified

### Dependency compatibility - much less needed changing than expected

Checked every import `training.py`/`TrainingKafkaDataset.py`/`utils.py`
actually uses against modern versions (torch 2.13.0, torchvision 0.28.0,
pytorch-ignite 0.5.5, avro 1.12.1, numpy 2.5.1, kafka-python 3.0.9),
**empirically, in a scratch `uv` venv, before assuming anything**:

- `avro.schema`/`avro.io.DatumReader`/`BinaryDecoder` - **still works
  unchanged**. Checked PyPI's JSON API directly (not a web search, per the
  lesson already learned in `mlcode_executor-litestar/pthexecutor`'s port):
  `avro` package has real, current releases supporting Python >=3.9
  (latest 1.12.1), unlike the TensorFlow side's `tensorflow-io` which
  genuinely died. **No swap to `fastavro` needed or done** - bumped the
  version pin only (`avro==1.11.0` -> `avro==1.12.1`). One API rename
  worth knowing: `avro.schema.Parse` (capital P, old versions) is now
  `avro.schema.parse` (lowercase) - not used by this file today, but would
  matter if the AVRO branch below is ever actually fixed.
- `ignite.contrib.handlers.TensorboardLogger`/`global_step_from_engine`,
  `ignite.handlers.ModelCheckpoint`, `ignite.engine.create_supervised_trainer`/
  `create_supervised_evaluator`, `ignite.metrics.*` wildcard - **all still
  work unchanged** under pytorch-ignite 0.5.5. Checked
  `inspect.signature()` on both `create_supervised_*` functions directly -
  every kwarg `training.py`'s `split_fit_params`/`split_val_params`
  forward (`non_blocking`, `prepare_batch`, `deterministic`, `amp_mode`,
  `scaler`, `gradient_accumulation_steps`, `output_transform`, etc.) is
  still a valid parameter name.
- `np.fromstring(reshape_str, dtype=int, sep=' ')` in
  `TrainingKafkaDataset.py` - **still works, no deprecation warning even**.
  The *text*-parsing mode of `fromstring` (`sep=` given) was never
  deprecated; only the binary-blob mode (`sep=''`, the historical
  `frombuffer`-alias usage) was. Confirmed by actually calling it under
  numpy 2.5.1 with warnings set to `'always'`.
- **Important**: `TensorboardLogger`/`ModelCheckpoint`/the `ignite.metrics.*`
  wildcard/`torchvision.models`/etc. look unused by `training.py`'s own
  code (no direct reference) - **do not remove them as dead imports**.
  `utils.py`'s `download_model()` does `exec(datatowrite, None, globals())`
  on the model code downloaded from the backend (which for `framework=
  'pth'` is the *raw Python source* of the model class, not a converted
  binary - see "Model code contract" below) - so these names are part of
  the exec-globals surface a submitted model's `metrics()`/`optimizer()`
  method can reference unqualified (e.g. `Accuracy()`, `Loss(...)`).
  Exact same gotcha already documented in
  `mlcode_executor-litestar/CLAUDE.md` for `tfexecutor`/`pthexecutor`'s
  `app.py` - first instinct to "clean up" these is wrong here too.

### Packaging

- `pyproject.toml`/`uv.lock` (new uv project, `requirements.txt` deleted).
  `requires-python = ">=3.12,<3.13"` matching `python:3.12-slim`. Pins:
  `torch==2.13.0`, `torchvision==0.28.0`, `pytorch-ignite==0.5.5`,
  `torchinfo==1.8.0`, `avro==1.12.1`, `kafka-python==3.0.9`,
  `numpy==2.5.1`, `scikit-learn==1.9.0`, `seaborn==0.13.2`,
  `requests==2.32.5` - all copied from `mlcode_executor-litestar/
  pthexecutor`'s already-settled, already-verified pins for consistency
  (same project, same PyTorch version story, no reason to re-derive).
- `[tool.uv.sources]` + explicit `pytorch-cpu` index (`download.pytorch.org/
  whl/cpu`), same pattern as `pthexecutor/pyproject.toml` - PyPI's plain
  `torch`/`torchvision` wheels are CUDA-bundled by default; this pattern
  gets the CPU-only build matching the default `python:3.12-slim` base
  image. `explicit = true` on the index matters (see `pthexecutor`
  CLAUDE.md's gotcha #5 for why) - without it, uv can quietly resolve
  unrelated packages against whatever's mirrored there instead of PyPI.
- `Dockerfile`/`start.sh`: uv-based pattern matching `tensorflow/` and
  `pthexecutor` (`uv sync --locked --no-install-project` then `uv sync
  --locked` in separate layers, `CMD ["./start.sh"]` -> `exec uv run
  training.py`). Base image bumped `python:3.8.6` (EOL) ->
  `python:3.12-slim`.
- Docker image builds clean: `kafka-ml-model-training-pytorch:test`. Both
  the bare `uv run` venv and the built container import `training.py`/
  `TrainingKafkaDataset.py`/`utils.py` with zero errors.

### The one real bug found and fixed (via real end-to-end testing)

`TrainingKafkaDataset.py`'s `__createconsumer__` did:
```python
consumer = KafkaConsumer(topic[0], bootstrap_servers=..., enable_auto_commit=False, group_id=group_id)
consumer.poll()
consumer.seek(tp, start_offset)
```
i.e. subscribe-style construction (positional `topic[0]` triggers
`subscribe()`), one bare `poll()` call, then an immediate `seek()`. This
raised `ValueError: Unassigned partition` on the real E2E run: a single
`poll()` isn't guaranteed to complete the consumer-group
join/rebalance (`FindCoordinator`/`JoinGroup`/`SyncGroup` round trips)
before `seek()` runs, so the partition may not be assigned to this
consumer yet.

**Fix**: `consumer.assign([tp])` before `.seek()` instead - synchronous,
no coordinator round trip needed at all, and this bounded offset-range
reader doesn't need group-managed assignment in the first place (it
already knows its own start/end offsets up front; `group_id` here only
ever mattered for the subscribe-based rebalance protocol this code
doesn't actually need).

**This exact fix already has a working precedent in this same repository**
- `KafkaModelEngine.__createconsumer__` (in *both*
  `federated-module/federated_model_training/tensorflow/KafkaModelEngine.py`
  and the original, untouched `model_training/tensorflow/
  KafkaModelEngine.py`) uses `consumer.assign([TopicPartition(...)])`
  **with a `# consumer.poll()` commented out directly above it** - a clear
  trace that the project's own original author already hit this identical
  problem once and fixed it this same way in that file, but never
  back-ported the fix to `TrainingKafkaDataset.py`. This is why the fix was
  applied here despite being, strictly, a **pre-existing bug rather than
  something the dependency upgrade itself broke** (no version-pinned
  evidence either way that kafka-python 2.0.2 was reliably immune to this
  race - it's an inherent timing assumption, not a guaranteed API
  contract, at any version) - it 100% blocks the *only* training path
  this module has, and the fix is trivial, safe, and not a new invention.
  Flag this reasoning if asked why this deviates from the stricter
  "byte-identical unless upgrade-broken" rule applied on the TensorFlow
  side.

### Model code contract (for constructing more test cases later)

Backend's `GET /results/{id}` for `framework == 'pth'` returns the
model's `code` field **as raw Python source text**, unlike TensorFlow
(which round-trips through `mlcode_executor-litestar/tfexecutor` to
produce an `.h5` file). `utils.py`'s `download_model()` just
`exec()`s it directly. The code must define a `model` variable holding an
`nn.Module` subclass instance with three additional required methods
(`optimizer()`, `loss_fn()`, `metrics()` - see the root `README.md`'s
"Something similar should be done in case you wish to use PyTorch"
section for the canonical example). Verified end-to-end with:
```python
class NeuralNetwork(nn.Module):
    def __init__(self):
        super(NeuralNetwork, self).__init__()
        self.linear_relu_stack = nn.Sequential(nn.Linear(1, 8), nn.ReLU(), nn.Linear(8, 2))
    def forward(self, x):
        return self.linear_relu_stack(x)
    def loss_fn(self):
        ce = nn.CrossEntropyLoss()
        return lambda y_pred, y: ce(y_pred, y.long())
    def optimizer(self):
        return torch.optim.Adam(model.parameters(), lr=0.001)
    def metrics(self):
        return {"accuracy": Accuracy(), "loss": Loss(self.loss_fn())}
model = NeuralNetwork()
```
Note the `.long()` cast in `loss_fn` - `TrainingKafkaDataset.__decodedata__`
decodes labels using whatever numpy dtype the datasource declares (e.g.
`uint8`), but `nn.CrossEntropyLoss` requires `torch.long` targets. This
cast is **test-model code, not a platform fix** - a real user hitting this
would need the same pattern (or a different loss), it's not something to
"fix" in `TrainingKafkaDataset.py` itself.

### Real end-to-end verification

Seeded a real `Configuration`/`MLModel` (`framework='pth'`, the model code
above)/`Deployment`/`TrainingResult` chain directly in `backend-litestar`'s
sqlite DB; sent 40 real RAW-format messages via `datasources-package`'s
`RawSink` (float32 `x` scalar, uint8 label, matching the TensorFlow side's
test data conventions); ran the actual trainer image as a pod with real
env vars. Confirmed, in order: model source download and `exec()` via
`GET /results/{id}`; Kafka control-topic consumption with correct
deployment-id filtering; the `consumer.assign()`-fixed bounded Kafka read
correctly replaying the 40-message range; `torch.utils.data.random_split`
producing the right 28/8/4 train/validation/test split
(`validation_rate=0.2`/`test_rate=0.1`); a real ignite `trainer.run(...)`
executing an actual training epoch; per-epoch metrics POSTed to
`results_metrics` (`"Metrics updated!"` logged); the held-out test
evaluator running (no error, though not separately confirmed against
expected values - out of scope, matches TF-side rigor); final trained
model (`torch.save(model.state_dict(), ...)`) + metrics uploaded via
`POST /results/{id}`, landing as `status: "finished"` with **no retry
loop** (confirms the earlier `backend-litestar` `status_code=200` fix on
`upload_result`/`upload_epoch_metrics` benefits this trainer too, not just
the TensorFlow one - same wire contract, same client-side `if
r.status_code == 200` check in this file's `send_epoch_metrics`/main
result-upload retry loop).

## Not verified / explicitly out of scope

- **AVRO input format** (`TrainingKafkaDataset.__decodedata__`'s
  `elif input_format == 'AVRO':` branch) - **not reachable, has multiple
  independent pre-existing bugs, confirmed dead code today regardless of
  this port**:
  1. `self.avro_decoder(input.value, reader_x)` calls a method that
     doesn't exist - the actual method is named `__avro_decoder__` (also
     itself missing a `self` parameter in its own definition: `def
     __avro_decoder__(msg_value, reader):`). Any invocation of this branch
     raises `AttributeError` immediately, before anything else in it runs.
  2. `DatumReader(data_scheme)` is called with a raw JSON-ish string, not
     a parsed `avro.schema.Schema` object (`avro.schema.parse(data_scheme)`
     needed first) - same class of bug already flagged in
     `mlcode_executor-litestar/CLAUDE.md` for `tfexecutor`'s `JsonDecoder`.
  3. The `label_reshape` branch reshapes `value.shape` a second time
     instead of `label.shape` - copy-paste bug.
  All three predate this port (confirmed - this whole method is
  byte-for-byte unchanged from `../../model_training/pytorch/
  TrainingKafkaDataset.py`) and are independent of any dependency version.
  **Flag if asked "does AVRO work for PyTorch training" - it does not, by
  a pre-existing bug, not by anything this port touched.** Did not fix,
  matching the same "flag, don't silently fix" stance applied everywhere
  else in this project for this exact class of dead-code bug.
- **Confusion matrix generation** (`CONF_MAT_CONFIG=true` branch) - not
  exercised in the E2E run above (ran with `CONF_MAT_CONFIG=false`).
  Uses `sklearn.metrics.confusion_matrix` + `seaborn.heatmap` +
  `matplotlib.pyplot.savefig` - all plain, well-established APIs with no
  version-specific concerns spotted during the import/signature checks
  above, so risk is assessed as low, but this specific code path was not
  actually run. Say so explicitly if asked.
- **GPU path** (`select_gpu()`, `pytorch/pytorch:*-cuda*-runtime` base
  image variant) - no GPU available in this dev environment, not tested,
  matches the same caveat already standard across this whole project.

## Remaining work

1. Write/update `README.md` for this directory (currently still the
   original, references `requirements.txt` and `pip install`).
2. Nothing else outstanding for the reachable path - this module's single
   training mode is fully verified.
