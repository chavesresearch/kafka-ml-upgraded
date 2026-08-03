# tf-kafka-dataset — instructions for AI assistants

A small, standalone, generically-useful package - **not** Kafka-ML
specific, despite living in this repo and being consumed by it. Extracted
from `model_training-upgraded/tensorflow/kafka_dataset.py` (itself already
duplicated into `federated-module-upgraded/federated_model_training/tensorflow/`)
during a "draft/PoC" pass explicitly requested to see whether this code
was worth publishing independently - the user's own framing was "people
can use it besides Kafka-ML."

## What it is

Two `tf.data.Dataset` sources built on `kafka-python`, replacing
`tensorflow-io`'s Kafka ops (`tensorflow_io.kafka.KafkaDataset`,
`tfio.experimental.streaming.KafkaBatchIODataset`) - `tensorflow-io` hasn't
shipped a release since mid-2023 and caps out at TensorFlow 2.16, so
nothing built on it works with any current TensorFlow. This is the same
blocker that hit `mlcode_executor-litestar/tfexecutor` and every TF
training container in this project - see
`model_training-upgraded/tensorflow/CLAUDE.md` for the original,
in-context writeup of the problem and the fix, before it was extracted
here.

## Consumers (both depend on this via a local `path` source, not a copy)

- `model_training-upgraded/tensorflow/mainTraining.py`
- `federated-module-upgraded/federated_model_training/tensorflow/federated_mainTraining.py`

Both `pyproject.toml`s reference this package via `[tool.uv.sources]`
(`tf-kafka-dataset = { path = "../../tf-kafka-dataset" }` or
`"../../../tf-kafka-dataset"` depending on nesting depth) - **not** git
submodules, PyPI, or a private index; this is a local, same-repo path
dependency, appropriate for a monorepo but not how a real standalone
release would be consumed.

## Docker build implication (the one real gotcha here)

Because both consumers depend on this via a **relative path outside their
own directory**, their Dockerfiles can no longer be built with their own
directory as the build context (`docker build .` from inside
`model_training-upgraded/tensorflow/`, the pattern used everywhere else in
this project) - `uv sync` would try to resolve `../../tf-kafka-dataset`
and fail to find it, since it's outside whatever got sent as the build
context. Both Dockerfiles were updated to expect the **repo root** as
their build context instead:

```
docker build -f model_training-upgraded/tensorflow/Dockerfile \
  -t kafka-ml-model-training-tensorflow:test .
docker build -f federated-module-upgraded/federated_model_training/tensorflow/Dockerfile \
  -t kafka-ml-federated-model-training-tensorflow:test .
```

Each Dockerfile `COPY`s `tf-kafka-dataset` into the image at whatever
absolute path makes the *relative* path from the trainer's own
`pyproject.toml` resolve correctly (`/usr/tf-kafka-dataset` for
`model_training-upgraded/tensorflow` - two directories up from
`/usr/src/app`; `/tf-kafka-dataset` for the federated trainer, which sits
one directory deeper, hence three levels up) - get this wrong and `uv
sync --locked --no-install-project` fails immediately with `Distribution
not found at: file://...` (hit exactly this once while wiring it up -
fixed by recomputing the actual directory depth rather than assuming it
matched the other Dockerfile). A root-level `.dockerignore` was added
too, since the build context is now the whole repo, not just one service
directory - without it, "sending build context to Docker daemon" would
otherwise include every other service's `.venv`/`node_modules`/etc.

Both images were rebuilt and verified after this change: real imports in
the running container, and (for `model_training-upgraded/tensorflow`) a
real re-run of `integration-tests/test_case1_single_classic.py` against
the rebuilt image - passed, same as before the extraction.

## Status

A draft/PoC, not a "for real" independent release: no version pin
strategy beyond matching whatever TensorFlow ceiling
`model_training-upgraded/tensorflow`'s own `pyproject.toml` already
settled on, no CI, no PyPI publish. If this is ever actually published
independently, decide then whether the two consumers should switch from a
local path dependency to a real version pin.
