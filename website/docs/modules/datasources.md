---
sidebar_position: 7
---

# datasources

`datasources/` is `kafkaml_datasources`, an installable Python package
(`src/` layout, built with `uv_build`) of client-side helper classes for
publishing training/inference data into Kafka in exactly the shape
Kafka-ML's training and inference containers expect. It's what the
[example scripts](../usage/single-models) and end-user data-ingestion
code import — `from kafkaml_datasources import RawSink`, etc. — as a
drop-in replacement for the original loose-files version of this
directory (same classes, same constructor signatures, same wire format).

This page is about how the package is built and what it puts on the
wire, not a tutorial on using it — see [Usage](../usage/single-models)
for that.

## Class hierarchy

Every sink except `AvroInference` derives from `KafkaMLSink`
(`sink.py`), which owns the shared machinery: constructing the
`KafkaProducer`/`KafkaConsumer`, tracking partition offsets, encoding
values to bytes, and publishing the control-topic message that tells
`backend` (by way of [kafka_control_logger](./kafka-control-logger))
that a dataset has been submitted.

| Class | Format | Notes |
|---|---|---|
| `RawSink` | RAW | Bounded/batch training data. Auto-detects `data_type`/`label_type`/reshape from the first `send()` call if not passed explicitly. |
| `AvroSink` | AVRO | Training data encoded against user-supplied Avro schema files (`data_scheme_filename`/`label_scheme_filename`). |
| `FederatedRawSink` | RAW | Same shape as `RawSink`, but defaults `control_topic` to `FEDERATED_DATA_CONTROL_TOPIC` and accepts `dataset_restrictions` — for federated learning's per-device data. |
| `OnlineRawSink` | RAW | Incremental/streaming variant — sends its control message immediately after auto-detecting format on the first message, instead of waiting for `close()`. |
| `OnlineFederatedRawSink` | RAW | Federated + incremental combination — control message is sent explicitly via `send_online_control_msg(data, label)`, not auto-detected. |
| `AvroInference` | AVRO | Standalone (does **not** subclass `KafkaMLSink`) — for publishing to an inference input topic, which has no control-topic/offset-tracking concept at all. |

## What `KafkaMLSink` does on construction and `close()`

Every sink builds both a `KafkaProducer` and a `KafkaConsumer` on
`__init__`, even though the consumer is never used to read actual
messages — it exists purely to query partition metadata
(`partitions_for_topic`, `end_offsets`) so the sink can report how many
messages it published. `__init_partitions` records each partition's
*current* end offset before any data is sent; `close()` (or, for the
online variants, the first `send()`) re-queries end offsets and diffs
them to compute `total_messages`.

`__get_partitions_and_offsets` uses one batched `KafkaConsumer.end_offsets()`
call per topic, not the older `assign()` → `seek_to_end()` → `position()`
sequence repeated per partition — `end_offsets()` doesn't require
`assign()` first and works across every partition of a topic in a single
broker round trip.

`close()` (bounded sinks) or `online_close()` (online sinks) flushes and
closes the producer, and closes the offset-lookup consumer with
`autocommit=False` — this consumer was never part of a real consumer
group doing work, so there's nothing meaningful to commit.

## Wire format

### Data messages

`KafkaMLSink.__object_to_bytes` encodes a value for use as a Kafka
message key or value, and only understands `bytes`, `bool`, `int`,
`float`, and `str`:

- `bool` → a single byte.
- `int` → a **4-byte little-endian**, signed encoding. This is
  decoded on the training side by `tf.io.decode_raw`, which defaults to
  little-endian when `little_endian=False` isn't explicitly passed
  (`model_training/tensorflow/utils.py`'s `decode_raw`) — and matches
  what NumPy's own `.tobytes()` already produces on the little-endian
  platforms this runs on, which is how `RawSink` and friends already
  encode wide-dtype labels (`label.tobytes()`) before this method ever
  sees a plain Python `int`.
- `float` → 4 bytes via `struct.pack("f", value)`.
- `str` → UTF-8 bytes.

`RawSink`/`FederatedRawSink`/`OnlineRawSink`/`OnlineFederatedRawSink`
all convert `data`/`label` with `.tobytes()` (they expect NumPy-array-like
inputs) before handing them to `KafkaMLSink.send`, which publishes with
the label as the Kafka message **key** and the data as the **value**.
`AvroSink.send_avro` instead serializes `data`/`label` (plain dicts
matching the configured Avro schema) with
`fastavro.schemaless_writer` into a reused `io.BytesIO` buffer, which is
truncated after each send.

### The control-topic message

On `close()` (or immediately after format auto-detection, for the online
variants), every `KafkaMLSink` subclass publishes one message to the
control topic (`KAFKA_ML_CONTROL_TOPIC` by default, or
`FEDERATED_DATA_CONTROL_TOPIC` for the federated sinks) — a JSON body
describing the dataset (`topic`, `input_format`, `input_config`,
`description`, `validation_rate`, `test_rate`, `total_msg`,
`dataset_restrictions`, `incremental`), keyed by a **4-byte big-endian**
encoding of the deployment id (`__deployment_id_to_bytes` — deliberately
the opposite endianness from the int label encoding above, since this
key is decoded generically by every consumer via
`int.from_bytes(msg.key, byteorder="big")`, not by `tf.io.decode_raw`).

This message is the origin of the entire datasource-registration flow:
[kafka_control_logger](./kafka-control-logger) consumes it from the
control topic and forwards it to `backend`'s `POST /datasources/`; both
[mlcode_executor](./mlcode-executor) (for int8 quantization calibration)
and the training containers also consume this same topic directly,
filtering by deployment id, to learn where and in what format to read
the actual training data.

## Relationship to `kafkaml-client` and example scripts

This package and [`kafkaml-client`](./kafkaml-client) are complementary,
not overlapping: `kafkaml-client` drives the REST side (define a model,
create a configuration, deploy it), while `kafkaml_datasources` drives
the data side (stream the actual training/inference data into Kafka once
a deployment exists). Every script under `../examples/*` imports sinks
from `kafkaml_datasources` directly; `kafkaml-client` does not wrap
datasource creation itself.

## Design choices worth knowing

- `shape_to_string`/`type_to_string` duck-type on `type(x).__name__`
  (checking for `"tf.Tensor"`/`"ndarray"` substrings) rather than
  importing TensorFlow/NumPy directly, so this package stays lightweight
  and doesn't force either dependency onto every consumer.
- `group_id` is accepted as a constructor parameter and passed to the
  internal offset-lookup consumer, even though the metadata queries it
  performs don't strictly require group membership — kept for API
  stability rather than trimmed.
- Avro encoding uses `fastavro` (not the unmaintained `avro-python3`),
  the same library `mlcode_executor/tfexecutor/decoders.py` uses on the
  decode side, so both ends of an Avro-format pipeline share one
  implementation.

## Testing

`tests/` (`uv run pytest -v`, CI via `.github/workflows/datasources.yml`)
fakes `KafkaConsumer`/`KafkaProducer` (`tests/conftest.py`'s
`patch_kafka` fixture), since every sink talks to Kafka the moment it's
constructed. It covers the deployment-id/label byte encodings, each
sink's auto-detect-format-on-first-send behavior (and the two variants
that deliberately skip it — `OnlineFederatedRawSink`, and `OnlineRawSink`
when pre-configured), and a real (not mocked) `fastavro` encode/decode
round trip for `AvroSink`/`AvroInference`. This is a fast, broker-free
regression suite; it doesn't replace end-to-end verification against a
real Kafka broker and a real `backend`/`kafka_control_logger` pair.

## See also

- [kafka-control-logger](./kafka-control-logger) — consumes the
  control-topic message this package publishes.
- [mlcode-executor](./mlcode-executor) — also consumes the control topic
  and the actual data topic, for int8 quantization calibration.
- [kafkaml-client](./kafkaml-client) — the complementary REST-side SDK.
- [model-training](./model-training) — the training containers reading
  the data this package publishes.
