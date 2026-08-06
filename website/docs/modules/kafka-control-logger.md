---
sidebar_position: 9
---

# kafka_control_logger

`kafka_control_logger/` is a small standalone process — a single file,
`logger.py` — that consumes Kafka-ML's control topic and relays every
message on it to `backend` over plain HTTP. It exists so `backend`
itself doesn't need to be a Kafka consumer at all: instead of every
service that cares about datasource registrations independently
consuming the control topic and calling into `backend`'s database
directly, this component does the consuming and `backend` just handles
one more REST endpoint. See the [backend page](./backend)'s "Why there's
no Kafka producer in this backend" section for the other half of that
design — `backend`'s `POST /datasources/` handler is pure DB persistence
specifically because this logger (not `backend`) owns the Kafka side.

Unlike per-deployment consumers such as `mlcode_executor` or
`model_training`, this component does **not** filter by deployment id —
its job is to archive *every* datasource submission into `backend`'s DB,
not just the ones relevant to one task.

## Flow

1. A `KafkaConsumer` (`kafka-python`) subscribes to `CONTROL_TOPIC` with
   `enable_auto_commit=False` and consumer group `logger`.
2. For each message, `build_datasource_payload` parses the JSON value
   (the same control-topic message body [datasources](./datasources)'
   `KafkaMLSink` classes publish — `topic`, `input_format`,
   `input_config`, `validation_rate`, `total_msg`, `description`), adds
   `deployment` (the message key, decoded with
   `int.from_bytes(msg.key, byteorder='big')`) and `time` (the Kafka
   message timestamp, converted with
   `datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()`).
3. `send_datasource_to_backend` `POST`s that payload as JSON to
   `http://{BACKEND}/datasources/`, retrying up to `RETRIES` (10) times
   with a 5-second sleep between attempts and a 30-second per-request
   timeout.
4. On success, the consumer commits **that specific message's offset**
   explicitly (`TopicPartition`/`OffsetAndMetadata`), not a bare
   `consumer.commit()`. A bare commit would sweep the offset forward to
   the consumer's *current* position — meaning if an earlier message had
   permanently failed, a later unrelated message's successful commit
   would silently mark the failed one as done too. Committing only the
   just-processed message's own offset avoids that.
5. If a message exhausts all `RETRIES` attempts, `send_datasource_to_backend`
   raises `BackendUnreachableError`, which propagates out of the consume
   loop uncaught and exits the process (`sys.exit(1)`). Kafka never
   advances past that message's offset, so restarting the pod redelivers
   it from the last real success — the intended behavior for a
   Kubernetes-managed pod that crashes and gets rescheduled.

## Configuration

Three required environment variables, read by `load_environment_vars`:

- **`BOOTSTRAP_SERVERS`** — Kafka broker list.
- **`BACKEND`** — hostname and port of `backend` (e.g. `backend:8000`).
- **`CONTROL_TOPIC`** — the Kafka control topic to consume.

## Testing

There's no dedicated automated test suite for this component; it's
exercised indirectly whenever an end-to-end scenario (real broker, real
`backend`) runs a training deployment, since that's what actually
publishes a control-topic message for this logger to forward.

## See also

- [backend](./backend) — the HTTP endpoint this logger calls
  (`POST /datasources/`), and why `backend` has no Kafka producer of its
  own.
- [datasources](./datasources) — the client package whose `KafkaMLSink.close()`
  publishes the control-topic message this logger consumes.
- [mlcode-executor](./mlcode-executor) — another, independent consumer of
  the same control topic (for int8 quantization calibration).
