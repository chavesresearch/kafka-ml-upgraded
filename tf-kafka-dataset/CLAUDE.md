# tf-kafka-dataset — instructions for AI assistants

A small, standalone, generically-useful package - **not** Kafka-ML
specific, despite living in this repo and being consumed by it. Extracted
from `model_training/tensorflow/kafka_dataset.py` (itself already
duplicated into `federated-module/federated_model_training/tensorflow/`)
during a "draft/PoC" pass explicitly requested to see whether this code
was worth publishing independently - the user's own framing was "people
can use it besides Kafka-ML."

## What it is

Two `tf.data.Dataset` sources built on `kafka-python`, replacing
`tensorflow-io`'s Kafka ops (`tensorflow_io.kafka.KafkaDataset`,
`tfio.experimental.streaming.KafkaBatchIODataset`) - `tensorflow-io` hasn't
shipped a release since mid-2023 and caps out at TensorFlow 2.16, so
nothing built on it works with any current TensorFlow. This is the same
blocker that hit `mlcode_executor/tfexecutor` and every TF
training container in this project - see
`model_training/tensorflow/CLAUDE.md` for the original,
in-context writeup of the problem and the fix, before it was extracted
here.

## Consumers (both depend on this via a local `path` source, not a copy)

- `model_training/tensorflow/mainTraining.py`
- `federated-module/federated_model_training/tensorflow/federated_mainTraining.py`

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
`model_training/tensorflow/`, the pattern used everywhere else in
this project) - `uv sync` would try to resolve `../../tf-kafka-dataset`
and fail to find it, since it's outside whatever got sent as the build
context. Both Dockerfiles were updated to expect the **repo root** as
their build context instead:

```
docker build -f model_training/tensorflow/Dockerfile \
  -t kafka-ml-model-training-tensorflow:test .
docker build -f federated-module/federated_model_training/tensorflow/Dockerfile \
  -t kafka-ml-federated-model-training-tensorflow:test .
```

Each Dockerfile `COPY`s `tf-kafka-dataset` into the image at whatever
absolute path makes the *relative* path from the trainer's own
`pyproject.toml` resolve correctly (`/usr/tf-kafka-dataset` for
`model_training/tensorflow` - two directories up from
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
the running container, and (for `model_training/tensorflow`) a
real re-run of `integration-tests/test_case1_single_classic.py` against
the rebuilt image - passed, same as before the extraction.

## Automated test suite + CI (2026-08-07)

`tests/` (11 tests, `uv run pytest -v`, CI via `.github/workflows/
tf-kafka-dataset.yml` - deliberately its own workflow, not folded into
`tensorflow_model_training.yml`'s `paths:` trigger, so this package's own
correctness is verified independently of whether `model_training/
tensorflow` happens to touch it that day). `kafka.KafkaConsumer` is faked
(`tests/conftest.py` - same broker-free-fake approach as `../datasources/
tests/conftest.py`, adapted for this package's different consumer usage:
`assign()`/`seek()`/iterate for `get_bounded_kafka_dataset`, `poll()` for
`get_streaming_kafka_batches`), but every dataset returned is a real,
actually-iterated `tf.data.Dataset` - proves the generator functions
produce the exact shape/values TensorFlow expects, not just that the
right consumer calls happened. Covers: exact offset-range bounding
(inclusive start, exclusive end), multi-partition and multi-topic specs
concatenating in declared order, value/key preservation, `group_id`
`str()` coercion (both functions), streaming's finite-vs-`-1` (infinite)
`stream_timeout` behavior including that `-1` keeps polling through empty
polls rather than giving up, and that the consumer is always `close()`d
once a generator is exhausted. Pinned `pytest==8.4.2`, matching
`../datasources`/`../kafkaml-client` - see either's identical comment for
why (`requires-python = ">=3.9"` here is a real compatibility promise,
not an implementation detail).

Same reasoning as `../datasources/CLAUDE.md`'s testing section: this is a
fast, broker-free *regression* check for routine changes to this file's
own logic - it doesn't replace the real, live-cluster verification
`model_training/tensorflow/CLAUDE.md` already documents (real CASE=1-9
runs against these exact dataset functions, against a real broker).

## Versioning

Bumped to `0.2.0` alongside the test suite above - no longer an entirely
untested draft. Still pre-1.0 (no external consumers beyond this repo's
own two, and no PyPI publish yet), so minor version bumps may still
include breaking changes; this isn't a promise of semver stability yet,
just an honest version number reflecting "now has a real regression
suite" vs. "didn't."

`tensorflow` is pinned `>=2.16,<3.0` in `pyproject.toml` - bounded, not
just a floor. `2.16` is the earliest version this package's `tf.data.
Dataset`/`TensorSpec` usage has ever actually been checked against; the
upper bound stops a future TF major version from being silently accepted
sight-unseen. CI installs whatever `>=2.16,<3.0` resolves to at the time
(currently `2.21.0`, matching the exact version both real consumers -
`model_training/tensorflow` and `federated-module/
federated_model_training/tensorflow` - pin) rather than pinning this
package's own CI to one hardcoded version, so a `uv sync` here stays
representative of what a real consumer's resolver would actually pick.

## Status

Still a monorepo-internal package, not a "for real" independent PyPI
release: consumed only via a local `path` dependency by the two trainers
above, no PyPI publish. The version pin strategy and CI above make it
independently testable and version-tracked *within this repo* - genuinely
publishing it externally is a separate decision, deferred until then
(along with whether the two consumers should switch from a local path
dependency to a real version pin at that point).
