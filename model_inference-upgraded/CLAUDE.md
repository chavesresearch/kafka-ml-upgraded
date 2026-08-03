# model_inference-upgraded — instructions for AI assistants

Sibling of `../model_inference` (kept untouched as reference/rollback).
Same faithful-port philosophy as `model_training-upgraded`: fix only what
each dependency upgrade actually broke, verify empirically. Much smaller
scope than `model_training-upgraded` - no `CASE` dispatch, no per-mode
class hierarchy, just one `inference.py` per framework that does real-time
single-message Kafka consume -> `model.predict()`/`model(x)` -> Kafka
produce, in a plain `while True: poll()` loop via `confluent_kafka`.

**Status: both `tensorflow/` and `pytorch/` are functionally complete and
verified end-to-end** against the live local cluster (using the already-
trained models from `model_training-upgraded`'s own verification pass -
`result_id=1` for TensorFlow, `result_id=7` for PyTorch).

## tensorflow/

- `requirements.txt` -> `pyproject.toml`/`uv.lock`. Pins:
  `tensorflow==2.21.0`, `confluent-kafka==2.15.0`, `fastavro==1.12.2`,
  `numpy==2.4.6` (same `>=3.11,<3.12` / numpy-2.4.6 pairing as
  `model_training-upgraded/tensorflow` - `tensorflow/tensorflow:2.21.0`'s
  base image ships Python 3.11, and numpy dropped cp311 wheels after
  2.4.x). No `web3`/blockchain dependency here at all, so (unlike the
  training side) **no `prerelease = "allow"` or `protobuf`
  override-dependencies needed** - don't copy that part of
  `model_training-upgraded/tensorflow/pyproject.toml` reflexively, check
  whether each module actually needs it.
- `decoders.py`'s `AvroDecoder` swapped from
  `tensorflow_io.experimental.serialization.decode_avro` to `fastavro`
  (`tensorflow-io` is dead, same recurring blocker as everywhere else in
  this project) - simpler than the training-side version since this
  `decode()` is called synchronously per Kafka message in a plain Python
  loop, never inside a traced `tf.data.Dataset.map()`, so no
  `tf.py_function` wrapping needed.
- `utils.py`'s `string_to_numpy_type` - same `np.float`/`np.string`/
  `np.bool` removed-alias fix as every other copy of this function in the
  project (`_NUMPY_TYPES` dict, `np.float` -> `np.float64` etc).
- **No Keras 3 `load_model()`/optimizer fix needed here** (unlike the
  training side) - inference only ever calls `model.predict()`, never
  `.fit()`, so the stale-optimizer-binding bug (see
  `model_training-upgraded/tensorflow/CLAUDE.md`) doesn't apply; verified
  this reasoning by actually running inference against a real trained
  model, not just assuming.
- Dockerfile bumped `tensorflow/tensorflow:2.7.0` -> `2.21.0`, uv-based
  layer pattern matching `model_training-upgraded/tensorflow`.

## pytorch/

- `requirements.txt` -> `pyproject.toml`/`uv.lock`. Pins copied from
  `model_training-upgraded/pytorch`'s already-settled, already-verified
  choices for consistency: `torch==2.13.0`, `torchvision==0.28.0`,
  `pytorch-ignite==0.5.5`, `avro==1.12.1`, `confluent-kafka==2.15.0`,
  `requests==2.32.5`. Same CPU-wheel `[tool.uv.sources]`/explicit-index
  pattern, same `python:3.12-slim` base image bump.
- `utils.py`'s `string_to_numpy_type` - same numpy-alias fix as everywhere
  else, even though this particular function turns out to be **dead code**
  in this file (`decoders.py`'s `RawDecoder` reads `configuration['data_type']`
  as a raw string and hands it straight to `np.frombuffer` - which accepts
  string dtype specifiers natively - never actually calling
  `string_to_numpy_type`). Fixed anyway for consistency/because it would
  still break the moment anyone did call it under modern numpy - cheap,
  correct, matches precedent everywhere else in this project.
- `avro`/`pytorch-ignite` - confirmed compatible unchanged (same finding as
  `model_training-upgraded/pytorch`'s CLAUDE.md - no code changes needed,
  just version pin bumps).
- **AVRO input format is dead code here too, same as the training side**:
  `AvroDecoder.decode(self, x, y)` takes 2 args but `inference.py` calls
  `decoder.decode(msg.value())` (1 arg) - `TypeError` on any real AVRO
  message, pre-existing (byte-identical to `../../model_inference/pytorch/
  decoders.py`), not fixed, matches the same "flag don't fix" stance
  applied to the identical bug shape in `model_training-upgraded/pytorch`.

## Real end-to-end verification (both frameworks)

Ran each framework's actual inference container as a pod against the live
cluster, `MODEL_URL`/`MODEL_ARCH_URL` pointing at the already-trained
results from `model_training-upgraded`'s own test pass (TensorFlow
`result_id=1`, PyTorch `result_id=7` - see that module's CLAUDE.md for what
those models are). Sent one real raw float32 Kafka message to a fresh
input topic, confirmed a real prediction landed on the output topic:

- **TensorFlow**: `{"values": [0.411990761756897, 0.588009238243103]}` -
  correct 2-class softmax output (sums to ~1.0) from the real trained
  `e2e-test-model`.
- **PyTorch**: `{"values": [[[-0.343..., -0.204...]]]}` - correct raw
  logits (2 values, no softmax - matches how the test model's
  `forward()` was written) from the real trained `e2e-pytorch-model`,
  though wrapped in extra list nesting. **Not a bug introduced by this
  port** - `inference.py` unconditionally runs every decoded input through
  `torchvision.transforms.ToTensor()`, which is really meant for
  image-shaped `(H, W, C)` arrays; handed a flat `(1,)` feature vector
  instead, it still runs (no crash) but adds shape padding along the way.
  Byte-identical to `../../model_inference/pytorch/inference.py` - a
  real consumer of this output would need to index into the extra
  wrapping, same as they would against the original, unmodified module.

## Not verified / explicitly out of scope

- **Distributed inference** (the `distributed=True` branch in
  `tensorflow/inference.py` - forwards low-confidence predictions to an
  "upper" model via `UPPER_BOOTSTRAP_SERVERS`/`OUTPUT_UPPER`/`LIMIT`) -
  not exercised. Reasoning for why it should still work, not confirmed:
  the per-submodel `.h5` files it downloads and serves are the same
  individual submodel architectures already verified end-to-end on the
  training side (`model_training-upgraded/tensorflow/CLAUDE.md`'s CASE=3
  section - each non-terminal submodel has exactly 2 outputs:
  features-to-forward + its own prediction, matching this file's
  `prediction_to_upper, prediction_output = model.predict(...)` unpacking).
  Say so explicitly if asked "is distributed inference tested" - it is
  not, by omission (time/scope), not because it's expected to fail.
- **AVRO input format** (both frameworks) - pre-existing dead code, see
  above.
- GPU path - no GPU in this dev environment, same caveat as everywhere
  else in this project.

## Remaining work

1. Update `README.md` in both `tensorflow/` and `pytorch/` (still describe
   `pip install -r requirements.txt`).
