---
sidebar_position: 10
---

# tf-kafka-dataset

`tf-kafka-dataset/` is a small, standalone Python package that provides
two `tf.data.Dataset` sources reading directly from Apache Kafka. It is
deliberately generic — nothing about its code is Kafka-ML-specific —
even though it lives inside this repository and is currently only
consumed by Kafka-ML's own TensorFlow trainers.

## Why it exists

TensorFlow's own Kafka integration lived in `tensorflow-io`
(`tensorflow_io.kafka.KafkaDataset` and
`tfio.experimental.streaming.KafkaBatchIODataset`). That package hasn't
shipped a release since mid-2023 and caps out at TensorFlow 2.16, so it
cannot be used with any current TensorFlow version. `tf-kafka-dataset`
re-implements both capabilities on top of the actively maintained
`kafka-python` client instead, yielding the same `(value, key)`
byte-string pair shape the old ops produced — an existing
`.map(lambda x, y: decode(x, y))` pipeline built against
`tensorflow-io`'s Kafka datasets works unmodified against these.

## Public API

The package's public surface, exported from
`src/tf_kafka_dataset/__init__.py`, is exactly two functions defined in
`src/tf_kafka_dataset/datasets.py`:

- **`get_bounded_kafka_dataset(topic_spec, bootstrap_servers, group_id)`**
  — replays an already-known offset range as a finite `tf.data.Dataset`.
  `topic_spec` is a comma-separated string of
  `"topic:partition:start_offset:end_offset"` entries (multiple
  partitions/topics can be combined in one dataset). Internally, for each
  entry, `_iter_bounded_partition` opens a `KafkaConsumer`, calls
  `consumer.assign([tp])` + `consumer.seek(tp, start_offset)`, and yields
  messages up to `end_offset`. `.assign()`/`.seek()` is used rather than
  `.subscribe()` because this reads a known, fixed range — there's no
  need for, or wait on, consumer-group rebalancing. This is the
  `KafkaDataset` replacement.

- **`get_streaming_kafka_batches(topic, bootstrap_servers, group_id,
  stream_timeout)`** — continuously polls a plain topic name (not an
  offset-range spec) and yields one small `tf.data.Dataset` per poll
  cycle that produced new messages. It is a generator you iterate
  directly, not a single `tf.data.Dataset` — each yielded mini-dataset
  still supports `len()`/`.take()`/`.skip()`/`.batch()` like any other
  in-memory dataset. `stream_timeout` is milliseconds of no new data
  before the generator stops; `-1` means poll forever, useful for
  continuous/indefinite training loops (internally this still polls in
  finite slices, defaulting to a 60s poll timeout, rather than handing
  `kafka-python` a literal infinite timeout). This is the
  `KafkaBatchIODataset` replacement. Because a new consumer group resumes
  from where it left off (`enable_auto_commit=False`, offsets tracked by
  the calling loop rather than committed automatically), re-running with
  the same `group_id` continues rather than re-reading from the start.

Both entry points coerce `group_id` to `str` — `kafka-python` requires a
string group id, unlike some older Kafka clients.

## Build and packaging

The package uses a standard `pyproject.toml` (`uv_build` backend),
depends on `kafka-python==3.0.10` and `tensorflow>=2.16`, and has no
compiled/native component — it's pure Python on top of `kafka-python`,
not a custom TensorFlow op registered against the C++ op registry.

## Relationship to the TensorFlow trainers

`tf-kafka-dataset` was extracted from
`model_training/tensorflow/kafka_dataset.py`, which had already been
duplicated once into
`federated-module/federated_model_training/tensorflow/`. Both trainers
now depend on the extracted package rather than keeping their own copies:

- `model_training/tensorflow/mainTraining.py`
- `federated-module/federated_model_training/tensorflow/federated_mainTraining.py`

Each consumer's `pyproject.toml` references it via `[tool.uv.sources]`
as a local `path` dependency (`tf-kafka-dataset = { path =
"../../tf-kafka-dataset" }`, or `"../../../tf-kafka-dataset"` for the
federated trainer, which sits one directory deeper) — not a git
submodule, not a PyPI package, not a private index. This is a monorepo
pattern appropriate for how the code is developed today, not how a
genuinely standalone release would typically be consumed.

### Docker build implication

Because both consumers reference this package via a relative path
*outside* their own directory, their Dockerfiles cannot be built with
their own directory as the build context — the pattern used everywhere
else in this project (e.g. `docker build .` from inside
`model_training/tensorflow/`, see [Building Kafka-ML](../installation/build)).
`uv sync` would try to resolve `../../tf-kafka-dataset` and fail, since
it falls outside whatever directory was sent as the build context.
Instead, both Dockerfiles expect the **repo root** as their build
context:

```bash
docker build -f model_training/tensorflow/Dockerfile \
  -t kafka-ml-model-training-tensorflow:test .
docker build -f federated-module/federated_model_training/tensorflow/Dockerfile \
  -t kafka-ml-federated-model-training-tensorflow:test .
```

Each Dockerfile `COPY`s `tf-kafka-dataset` into the image at whatever
absolute path makes the *relative* path from the trainer's own
`pyproject.toml` resolve correctly — `/usr/tf-kafka-dataset` for
`model_training/tensorflow` (two directories up from `/usr/src/app`),
and `/tf-kafka-dataset` for the federated trainer (three levels up,
since it sits one directory deeper in the tree). Getting this distance
wrong makes `uv sync --locked --no-install-project` fail immediately
with `Distribution not found at: file://...`. Since the build context is
now the whole repo rather than one service directory, a root-level
`.dockerignore` is also required — without it, the build context upload
would include every other service's `.venv`/`node_modules`/etc.

## Status

This is a draft/proof-of-concept extraction, not a "for real"
independent release: there is no version pin strategy beyond matching
whatever TensorFlow ceiling `model_training/tensorflow`'s own
`pyproject.toml` already settled on, no CI, and no PyPI publish. If it
is ever published independently, the two consumers would need to decide
whether to switch from a local path dependency to a real version pin.

## See also

- [model-training](./model-training) — the TensorFlow trainer that
  consumes this package via `mainTraining.py`.
- [federated-module](./federated-module) — its edge trainer consumes the
  same package via `federated_mainTraining.py`.
