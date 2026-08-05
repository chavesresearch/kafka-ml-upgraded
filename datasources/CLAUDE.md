# kafkaml-datasources — instructions for AI assistants

This is a reimplementation of the old loose-files `datasources/` (meant to
be copied into a project - preserved at `../../kafka-ml/datasources` as
historical reference) as a proper installable package,
`kafkaml_datasources` (`src/` layout, `pyproject.toml` + `uv.lock`, built
with `uv_build`). Same classes, same constructor signatures, same wire
format - a drop-in replacement requiring only an import-line change in
existing example scripts (`../examples/*/*.py`), not a rewrite of them.

**Status: adopted.** Every example under `../examples/*` imports from
`kafkaml_datasources` (e.g. `from kafkaml_datasources import RawSink`), not
the old `datasources.*` path - this package's real module name, not a bare
folder, so the old-style import never worked once this directory was
renamed into `datasources`' place.

## Why this exists alongside `kafka_control_logger` and `backend` work

This package's control-topic message (`KafkaMLSink.__send_control_msg`) is
the *origin* of the whole datasource-registration flow: a client script
calls `.close()`, which publishes directly to Kafka's control topic;
`../kafka_control_logger` consumes that topic and forwards each message to
`backend`'s `POST /datasources/`. All three were touched in the same
session because a bug in any one of them only becomes obvious when you
trace the whole chain - see `../backend/CLAUDE.md`'s bug #7 (the republish
loop) for the finding that started this.

## What changed vs. the original (`../../kafka-ml/datasources`)

1. **Avro: `avro-python3` → `fastavro`.** `avro-python3` hasn't shipped a
   release since March 2021 (its Python 3 support was folded back into the
   official `avro` package years ago - don't reach for `avro-python3`
   again without checking PyPI first). `fastavro` is what
   `mlcode_executor/tfexecutor/decoders.py` already uses for the
   matching *decode* side of Avro-format datasources, so both ends of the
   pipeline now share one library. `avro.io.DatumWriter`/`BinaryEncoder`
   became `fastavro.schemaless_writer(fileobj, parsed_schema, record)` -
   same calling convention from the outside (`send_avro(data, label)`
   still takes plain dicts matching the schema).
2. **Offset tracking batched, not restructured.** The original
   `__get_partitions_and_offsets` did, per partition:
   `consumer.assign([tp])` → `consumer.seek_to_end(tp)` →
   `consumer.position(tp)` - three broker interactions per partition, and
   `assign()` mutates the consumer's partition assignment as a side effect
   every single call. Replaced with one `consumer.end_offsets(partitions)`
   call covering every partition of the topic at once. This does **not**
   need `assign()` first - confirmed by reading `KafkaConsumer.end_offsets`'s
   docstring in a scratch venv ("does not change the current consumer
   position") before relying on it.

   This does *not* eliminate the `KafkaConsumer` from `KafkaMLSink`
   entirely, and deliberately doesn't try to track exact offsets via
   producer-send futures instead (`producer.send(...)` returns a future
   that resolves to the exact partition+offset written) - that would be
   more precise per-message, but doesn't cleanly generalize to
   multi-partition topics (you'd need to resolve every future to find the
   min/max offset *per partition*, which isn't cheaper than just asking the
   broker for `end_offsets` twice). The two-touchpoint "ask the broker"
   design (once at session start, once at `close()`) is correct and
   necessary for the multi-partition case; only the *manual per-partition
   loop* within each touchpoint was the inefficiency.
3. **Deployment id key widened to 4 bytes**, in a new
   `KafkaMLSink.__deployment_id_to_bytes`, used only by
   `__send_control_msg`/`__send_online_control_msg`. The original
   `__object_to_bytes(self.deployment_id)` produced `bytes([deployment_id])`
   - a single byte, raising `ValueError` for any id ≥ 256.
   `__object_to_bytes` itself is unchanged and still used for *labels* on
   data messages (a completely different wire contract - int/bool as 1
   byte, float via `struct.pack("f", ...)`, str as utf-8 - decoded by
   `mlcode_executor`/training containers) - don't merge these two encoders,
   they serve different consumers with different expectations.
4. **`kafka-python` bumped `2.0.2` → `3.0.9`.**

## Automated test suite (2026-08-06)

`tests/` (43 tests, `uv run pytest -v`, CI via `.github/workflows/
datasources.yml`) - didn't exist before this date, only the one-off
manual real-broker verification below. `KafkaConsumer`/`KafkaProducer`
are faked (`tests/conftest.py`'s `patch_kafka` fixture) since every Sink
talks to Kafka the moment it's constructed - covers the deployment-id
encoding fix, every Sink subclass's auto-detect-format-on-first-send
behavior (including the two that deliberately don't:
`OnlineFederatedRawSink`, and `OnlineRawSink` when pre-configured), and a
real (not mocked) `fastavro` encode/decode round trip for
`AvroSink`/`AvroInference`. Pinned `pytest==8.4.2`, not the `9.x` used
elsewhere in this repo - `9.x` dropped Python 3.9 support, and this
package's own `requires-python = ">=3.9"` is a real compatibility promise
to callers, not an internal implementation detail to bump freely. This
suite is a fast, broker-free *regression* check for routine changes - it
deliberately doesn't try to replace the real-broker verification below.

## Verified with a real broker - not just inspection

A single-broker Kafka (Docker, KRaft mode, `apache/kafka:latest`) was
actually started and exercised end-to-end:

```bash
docker network create kafkaml-e2e-test
docker run -d --name kafka --network kafkaml-e2e-test -p 19092:9092 \
  -e KAFKA_NODE_ID=1 -e KAFKA_PROCESS_ROLES=broker,controller \
  -e KAFKA_LISTENERS=PLAINTEXT://:9092,CONTROLLER://:9093 \
  -e KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://kafka:9092 \
  -e KAFKA_CONTROLLER_LISTENER_NAMES=CONTROLLER \
  -e KAFKA_CONTROLLER_QUORUM_VOTERS=1@localhost:9093 \
  -e KAFKA_LISTENER_SECURITY_PROTOCOL_MAP=CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT \
  -e KAFKA_INTER_BROKER_LISTENER_NAME=PLAINTEXT \
  -e KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1 \
  -e KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR=1 \
  -e KAFKA_TRANSACTION_STATE_LOG_MIN_ISR=1 \
  -e CLUSTER_ID=<any 22-char string> \
  apache/kafka:latest
```

Then a `RawSink` (built from this package, installed via `pip install
/pkg` in a throwaway `python:3.12-slim` container on the same network) with
**`deployment_id=300`** (>255, the old encoding's ceiling) sent 5 messages
and closed. `../kafka_control_logger`'s container picked up the control
message and forwarded it to a `../backend` container (seeded with a
matching `Deployment` row via `alembic upgrade head` + `async_sessionmaker`,
same approach `backend/CLAUDE.md` recommends). Result: exactly one
`Datasource` row via `GET /datasources/`, key correctly round-tripped as
`300` through the 4-byte encoding, and - waiting 15+ seconds afterward -
the row count stayed at 1 (confirming the republish-loop fix in `backend`
actually holds, not just in theory).

**Gotcha hit along the way, unrelated to this package's own code**: a
fresh single-broker Kafka's `__consumer_offsets` internal topic defaults to
`replication.factor=3`, which can't be satisfied by 1 broker -
`kafka_control_logger`'s consumer group join silently hangs forever (no
error, just stuck after "Updated metadata..." with no join-group progress)
until `KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1` (and the transaction-log
equivalents, since `kafka-python`'s producer defaults to idempotent mode)
are set on the broker. Not a code bug - a test-harness-only concern - but
worth remembering if a future single-broker test setup seems to hang with
no errors: check `docker logs <broker>` for
`INVALID_REPLICATION_FACTOR` before assuming the client code is at fault.

## Design choices carried over unchanged (not oversights)

- `group_id` is still accepted as a constructor parameter and still passed
  to the internal offset-lookup `KafkaConsumer`, even though pure metadata
  queries (`partitions_for_topic`, `end_offsets`) don't strictly need group
  membership. Left as-is to avoid a public API change beyond what "more
  efficient" required - removing it is a separate, larger decision.
- `shape_to_string`/`type_to_string` duck-type on `type(x).__name__`
  (checking for `"tf.Tensor"`/`"ndarray"` substrings) instead of importing
  TensorFlow/numpy directly - deliberate, so this package stays lightweight
  and doesn't force a TF/numpy install on every consumer of it. Don't "fix"
  this by adding a real numpy/tensorflow dependency.
