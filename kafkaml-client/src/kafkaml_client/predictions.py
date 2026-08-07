"""Optional real-time-inference request/response support.

`send_dataset` (`datasets.py`) closes the loop on getting training data
*into* Kafka; `predict_one`/`predict_batch` here close the loop on the
other side - sending input row(s) to a deployed real-time inference's
input topic and reading the prediction(s) back from its output topic.
There's no dedicated SDK class for this in `kafkaml_datasources` either
(it only has `AvroInference`, for the AVRO case) - RAW-format inference
I/O is just plain Kafka topics by design, so every
`examples/*/*_dataset_inference_example.py` script hand-rolls a plain
`kafka.KafkaProducer`/`KafkaConsumer` pair to do this.

Requires the `datasets` extra (``pip install kafkaml-client[datasets]``),
same as `datasets.py` - imports are lazy, so plain `import kafkaml_client`
never requires `kafka-python`/`numpy`/`pandas`.
"""

from __future__ import annotations

import json
from typing import Any


def _import_kafka():
    try:
        from kafka import KafkaConsumer, KafkaProducer
    except ImportError as e:  # pragma: no cover - exercised via a real missing-import test
        raise ImportError(
            "predict_one/predict_batch need the 'datasets' extra: "
            "pip install 'kafkaml-client[datasets]' (pulls in kafka-python)."
        ) from e
    return KafkaConsumer, KafkaProducer


def _row_to_bytes(row: Any) -> bytes:
    """Converts one input row to the raw bytes a real-time inference
    deployment expects on its input topic - a pandas `Series`/`DataFrame`
    row is converted via `.to_numpy()` first (same as `datasets.py`'s
    `_to_numpy`), then `.tobytes()` (matching
    `examples/*/*_dataset_inference_example.py`'s `x_test[i].tobytes()`)."""
    to_numpy = getattr(row, "to_numpy", None)
    if callable(to_numpy):
        row = to_numpy()
    return row.tobytes()


def predict_batch(
    bootstrap_servers: str,
    input_topic: str,
    output_topic: str,
    rows: list[Any],
    *,
    timeout_ms: int = 60000,
    group_id: str = "kafkaml-client",
) -> list[dict[str, Any]]:
    """Sends every row in `rows` (each a numpy `ndarray`, or a pandas
    `Series`/`DataFrame` row, converted via `.to_numpy()`) to `input_topic`,
    then reads back `len(rows)` JSON predictions from `output_topic` -
    each the same `{"values": [...]}`-shaped body a deployed real-time
    inference publishes. Returns predictions in the order they arrived on
    `output_topic` (matching send order for a single-partition topic, the
    standard shape for a Kafka-ML deployment's input/output topics).

    Raises `TimeoutError` if fewer than `len(rows)` predictions arrive
    within `timeout_ms`.

    The output consumer is explicitly configured with
    `auto_offset_reset="earliest"` - **not** `kafka-python`'s own default
    (`"latest"`). A consumer created with the default can join its
    consumer group *after* a fast real-time inference deployment has
    already produced the prediction(s), and then silently see nothing;
    this was a real bug found (and fixed, in 6 places) in this project's
    own `examples/*/*_dataset_inference_example.py` scripts - baked in
    here so a caller of this SDK can't hit the same trap.
    """
    KafkaConsumer, KafkaProducer = _import_kafka()

    consumer = KafkaConsumer(
        output_topic,
        bootstrap_servers=bootstrap_servers,
        group_id=group_id,
        auto_offset_reset="earliest",
        consumer_timeout_ms=timeout_ms,
    )
    producer = KafkaProducer(bootstrap_servers=bootstrap_servers)
    try:
        for row in rows:
            producer.send(input_topic, _row_to_bytes(row))
        producer.flush()

        predictions: list[dict[str, Any]] = []
        for msg in consumer:
            predictions.append(json.loads(msg.value.decode("utf-8")))
            if len(predictions) == len(rows):
                break
    finally:
        producer.close()
        consumer.close()

    if len(predictions) < len(rows):
        raise TimeoutError(
            f"expected {len(rows)} prediction(s) on {output_topic!r}, "
            f"got {len(predictions)} within {timeout_ms}ms"
        )
    return predictions


def predict_one(
    bootstrap_servers: str,
    input_topic: str,
    output_topic: str,
    row: Any,
    *,
    timeout_ms: int = 60000,
    group_id: str = "kafkaml-client",
) -> dict[str, Any]:
    """`predict_batch` for a single input row - sends `row`, returns the
    one prediction read back from `output_topic`. See `predict_batch` for
    the full behavior (including why the output consumer always reads
    from `"earliest"`)."""
    return predict_batch(
        bootstrap_servers,
        input_topic,
        output_topic,
        [row],
        timeout_ms=timeout_ms,
        group_id=group_id,
    )[0]
