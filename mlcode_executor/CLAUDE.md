# Kafka-ML Litestar mlcode_executor — instructions for AI assistants

This is a port of the original Flask-based `mlcode_executor` (TensorFlow
2.7.0 / PyTorch 1.10.0), preserved at `../../kafka-ml/mlcode_executor` as
historical reference, to [Litestar](https://litestar.dev/) - the same
stack `../backend` uses - plus a general dependency upgrade to current
stable releases (TensorFlow 2.21.0, PyTorch 2.13.0, etc; see each service's
`pyproject.toml`). Dependencies are managed with [uv](https://docs.astral.sh/uv/)
(`pyproject.toml` + `uv.lock`, no `requirements.txt`), matching `../backend`.
The old Flask version is the reference implementation for behavior: same
URL paths (`/exec_tf/`, `/exec_pth/`, `/check_deploy_config/`,
`/convert_to_tflite/`), same request/response shapes and status codes, so
`../backend` can point at this service without any backend-side changes -
just repoint `TFEXECUTOR_URL`/`PTHEXECUTOR_URL`.

**Status: this is the deployed executor.** See `kustomize/base/resources/
tfexecutor-deployment.yaml` / `pthexecutor-deployment.yaml`, which point
at this port's images (`kafka-ml-tfexecutor`, `kafka-ml-pthexecutor` -
same names the old Flask images used, confirmed against
`kustomize/master/kustomization.yaml`'s `images:` transformer).

## Two independent services, two independent upgrade stories

- `tfexecutor/` - TensorFlow. Bumping TF to latest **broke `tensorflow-io`**
  (last release mid-2023, caps at TF 2.16, no maintained fork), which the
  Flask version used for two things: streaming Kafka directly into a
  `tf.data.Dataset` for int8-quantization calibration
  (`tensorflow_io.kafka.KafkaDataset`) and Avro decoding
  (`tfio.experimental.serialization.decode_avro`). Both were replaced, not
  just version-bumped - see "Gotchas" below.
- `pthexecutor/` - PyTorch. No equivalent blocker; torch/torchvision/ignite
  don't have a Kafka or serialization dependency baked in, so this one is a
  much more direct Flask→Litestar port with no architecture changes.

## Stack

- [Litestar](https://litestar.dev/) 2.24.0 - same as `../backend`
- `uvicorn[standard]` instead of `gunicorn` - unlike `../backend`,
  neither service has a `web3`-style `websockets<10` conflict, so the
  `[standard]` extra (pulls in `websockets`, `uvloop`, `httptools`) is fine
  here; no need for the plain-uvicorn/`wsproto` workaround.
- `kafka-python==3.0.9` (tfexecutor only) - it's actively maintained again
  (contrary to its reputation from a couple of years ago; verify current
  status before assuming otherwise if it comes up again). Kept instead of
  switching to `aiokafka` (what `../backend` uses) because the
  consumption here is a single bounded, sequential, blocking operation (wait
  for one control message, then stream up to N data messages) driven from a
  synchronous `def` handler - there's no concurrency to gain from async here,
  and introducing a second Kafka client library into this one service for
  no functional benefit isn't a win.
- `fastavro==1.12.2` (tfexecutor only) - replaces tensorflow-io's Avro
  decode op, see above.

## Gotchas learned the hard way (keep these)

1. **Litestar does not run sync `def` handlers in a thread pool unless you
   pass `sync_to_thread=True` on the route decorator.** Without it, Litestar
   emits a `LitestarWarning` and calls the sync function directly on the
   event-loop thread - blocking it for the duration of the call. Every
   handler here wraps genuinely blocking work (TF/torch model exec,
   training, a blocking Kafka consumer loop), so every one of them needs
   `sync_to_thread=True` explicitly. Verified this against Litestar's
   source (`litestar/handlers/http_handlers/base.py`,
   `litestar/utils/sync.py`) rather than assuming FastAPI/Starlette-style
   automatic offloading - Litestar's default without the flag is *not* to
   offload.
2. **`convert_to_tflite` (tfexecutor) can't use that pattern** - it needs
   `await request.form()` to read the multipart body, so it's `async def`
   instead. The actual blocking conversion work is offloaded manually via
   `await anyio.to_thread.run_sync(...)`, the same pattern
   `../backend/app/controllers/iot_devices.py` already uses for
   `send_mqtt_message_to_tasmota`.
3. **The uploaded file's multipart field name IS the model filename** (e.g.
   `"42.h5"`), not a fixed field like `"file"` - this is a real wire
   contract with both backends
   (`files={f"{result_id}.h5": model_path.read_bytes()}` in
   `iot_devices.py`), not an accident to clean up. Since Litestar's
   structured multipart parsing (`Body(media_type=RequestEncodingType.
   MULTI_PART)`) needs known field names, this handler instead takes the
   raw `Request` and calls `await request.form()`, then scans
   `form.items()` for an `UploadFile` value whose field name ends in
   `.h5` - confirmed this is the right approach by reading Litestar's
   `Request.form()`/`FormMultiDict`/`UploadFile` source directly (installed
   litestar in a scratch venv and used `inspect.getsource` - the fetched
   docs page was thin/uncertain on this exact case).
4. **litestar==2.24.0 depends on the `multipart` package, not
   `python-multipart`** - `../backend`'s `pyproject.toml` (pinned
   to litestar==2.14.0 at the time) pinned `python-multipart==0.0.20`;
   that's stale advice for this litestar version. Confirmed via `pip show
   litestar` in a scratch venv, not assumed from the older sibling project.
5. **PyTorch's PyPI wheel isn't CPU-only by default** - plain `torch==2.13.0`
   from PyPI pulls the CUDA-bundled build (with `nvidia-*-cu12`
   dependencies). To get the lightweight CPU build matching the default
   `python:3.12-slim` base image, `pthexecutor/pyproject.toml` adds
   `download.pytorch.org/whl/cpu` as a named `[[tool.uv.index]]` with
   `explicit = true`, and pins `torch`/`torchvision` to it via
   `[tool.uv.sources]`. `explicit = true` matters: without it, uv's
   dependency-confusion protection still treats the extra index as a
   general fallback and can quietly resolve *unrelated* packages (numpy, in
   an earlier draft of this lock) against whatever happens to be mirrored
   there instead of PyPI's latest - `explicit = true` scopes the index to
   only the packages that opt in via `tool.uv.sources`.
6. **`tfexecutor` and `pthexecutor` are pinned to *different* Python
   versions, on purpose.** `pthexecutor` uses `python:3.12-slim` (our
   choice), but `tfexecutor` is pinned to `>=3.11,<3.12` because the
   official `tensorflow/tensorflow:2.21.0` Docker image actually ships
   Python 3.11.x, not 3.12 - confirmed by running
   `docker run --rm tensorflow/tensorflow:2.21.0 python3 --version`, not
   assumed. This cascades into the numpy pin: numpy dropped Python 3.11
   wheels as of 2.5.x, so `tfexecutor` is pinned to `numpy==2.4.6` (the
   last release with a cp311 wheel) while `pthexecutor` uses `numpy==2.5.1`.
   If TF's base image ever ships a newer Python, both the `requires-python`
   bound and the numpy pin in `tfexecutor/pyproject.toml` should be
   revisited together.
7. **Module-level imports in both `app.py` files aren't all "used" by this
   file's own code - some exist purely to populate the `exec()` namespace
   for user-submitted model code.** `exec_model()` runs
   `exec(model_code, None, globals())`, so whatever's bound in this
   module's globals (via plain imports) is what a user's submitted model
   code can reference unqualified (e.g. `keras.Sequential(...)` or
   `Accuracy()` inside a Kafka-ML model definition). Concretely:
   `tfexecutor/app.py` keeps `from tensorflow import keras` and
   `import tensorflow_datasets as tfds` even though neither name appears
   elsewhere in the file; `pthexecutor/app.py` keeps
   `from ignite.metrics import *` even though only `Loss` is used directly.
   First draft of this port "cleaned up" both as unused/wildcard imports -
   wrong, would have silently broken any submitted model code relying on
   them being pre-bound. If you touch these files, check whether a name is
   part of this exec-globals surface before removing it as unused.

## Bugs/dead weight found in the Flask version and fixed here

1. `decoders.py`'s numpy type table used `np.float`/`np.string`/`np.bool` -
   all three were removed as aliases in NumPy 1.24 (mid-2023); would raise
   `AttributeError` on any current NumPy regardless of the Litestar port.
   Replaced with their actual underlying types (`np.float64`, `np.bytes_`,
   `np.bool_`) - same resolved dtype, just spelled correctly.
2. `convert_to_tflite` (tfexecutor) wrote the converted model to a
   `.tflite` file on disk and immediately read it back before responding -
   `TFLiteConverter.convert()` already returns the flatbuffer bytes
   directly. Simplified to skip the round-trip; not a behavior change.
3. `pthexecutor`'s `pytorch_executor` exception handler swallowed the
   exception without logging it (`except Exception as e: return
   Response(status=400)` - `e` unused). Now logged, matching tfexecutor's
   handler.

## Things intentionally preserved, not "fixed"

- The `.h5`-suffix-as-field-name multipart contract (see Gotcha 3) - looks
  odd, is load-bearing.
- `parse_kwargs_fit`-style trust model: this whole platform already
  `exec()`s user-submitted model code (`exec_model` in both `app.py`
  files) - not hardened here, matching `../backend`'s documented
  stance on the same tradeoff in its own `CLAUDE.md`.
- `pthexecutor`'s `input_shape` endpoint TODO comment (uncertain torch
  input-shape API) - carried over verbatim, not resolved, since resolving
  it wasn't in scope for this port.

## Pre-existing bug noticed but NOT fixed (flag if it comes up)

`tfexecutor/decoders.py`'s `JsonDecoder.decode(self, x)` takes one argument,
but `app.py`'s `retrieve_representative_dataset` always calls
`decoder.decode(msg.value, msg.key)` (two args) regardless of which decoder
`DecoderFactory` returned. This means int8-quantization calibration for a
deployment whose datasource uses `input_format: JSON` would raise
`TypeError` the first time it tries to decode a sampled message. This bug
predates this port - the original Flask `tfexecutor` had the exact same
`.map(lambda x, y: decoder.decode(x, y))` call site, unconditional on
decoder type - so it's carried over unchanged rather than silently
fixed. Worth fixing if int8 quantization over JSON-format datasources is
actually something anyone uses; wasn't touched here since it's orthogonal
to the Flask→Litestar port and the TF dependency upgrade.

## Testing approach

- Verified every version pin in both `pyproject.toml` files against PyPI's
  JSON API directly (`https://pypi.org/pypi/<pkg>/json`), not search
  summaries - a couple of web searches during this port gave confidently
  wrong or self-contradictory version/date info (e.g. claiming
  `kafka-python` was unmaintained when PyPI shows active 2026 releases;
  inconsistent PyTorch release dates across two search calls). Don't trust
  a web search's summarized version/date claims for fast-moving packages -
  hit the PyPI JSON API instead.
- Verified the exact Litestar multipart/sync-to-thread/dependency-name
  behavior (Gotchas 1, 3, 4) by installing `litestar==2.24.0` in a scratch
  venv and reading its actual source with `inspect.getsource`, since the
  fetched documentation pages were thin or uncertain on these specific
  points.
- **Both services were actually `uv sync`'d and imported for real** (not
  just `py_compile`): `uv add --python 3.11 ...` / `uv add --python 3.12
  ...` resolved and installed the real `tensorflow==2.21.0` and
  `torch==2.13.0+torchvision==0.28.0` (CPU build) into project `.venv`s,
  and `python -c "import app"` succeeded for both, with TF logging
  `Num GPUs Available: 0` as expected on a CPU-only dev machine. This is
  what caught the Python-3.11-vs-3.12 / numpy-2.4.6-vs-2.5.1 split (Gotcha
  6) - it wasn't discoverable from reading PyPI metadata alone, only by
  actually running `docker run tensorflow/tensorflow:2.21.0 python3
  --version` and then hitting a real `uv add` resolution failure.
- Verified the Docker base image tags referenced in both `Dockerfile`s
  (`tensorflow/tensorflow:2.21.0[-gpu]`,
  `pytorch/pytorch:2.13.0-cuda12.6-cudnn9-runtime`) against Docker Hub's API
  directly, and confirmed the `tensorflow/tensorflow:2.21.0` image's actual
  Python version by running it, not assuming from wheel availability.

Still needed as of this writing: a `docker build` of both `Dockerfile`s
(the local `.venv` installs above prove the dependency resolution is
sound, but not that the multi-stage `uv sync --no-install-project`
layering or the TF/PyTorch base images themselves work) and an end-to-end
exercise against a real Kafka broker (in particular, the rewritten
`retrieve_representative_dataset` Kafka-sampling path in
`tfexecutor/app.py` - int8 quantization is the one code path in this port
with no tensorflow-io equivalent to diff against). `integration-tests/`
does exercise `/exec_tf/`/`/exec_pth/` indirectly (every model create goes
through `_check_model_code` → this service), but not the int8-quantization
path specifically. Say so explicitly rather than claiming this was tested
if asked.
