"""Optional numpy/pandas dataset -> Kafka datasource support.

Every `examples/*/*_dataset_training_example.py` script in this repo
hand-rolls the same few lines to get a numpy dataset into Kafka-ML:
construct a `kafkaml_datasources.RawSink`, loop over the data sending one
row at a time, then `.close()` it (which is what actually registers the
datasource - `close()` publishes a control-topic message that
`kafka_control_logger` forwards to the backend's `POST /datasources/`,
there's no separate REST call). `send_dataset`/`send_dataframe` below
wrap that pattern as one call, for numpy arrays or pandas Series/
DataFrames directly.

Requires the `datasets` extra (``pip install kafkaml-client[datasets]``),
which pulls in `kafkaml-datasources`, `numpy`, and `pandas` - kept out of
the base package's dependencies so a caller who only wants the REST
client (`KafkaMLClient`) doesn't pay for a numpy/pandas/kafka-python
install they'll never use. Every import here is done lazily, inside the
functions, not at module level - `import kafkaml_client` alone never
requires any of them; only actually calling one of these does.
"""

from __future__ import annotations

from typing import Any


def _import_raw_sink():
    try:
        from kafkaml_datasources import RawSink
    except ImportError as e:  # pragma: no cover - exercised via a real missing-import test
        raise ImportError(
            "send_dataset/send_dataframe need the 'datasets' extra: "
            "pip install 'kafkaml-client[datasets]' (pulls in "
            "kafkaml-datasources, numpy, and pandas)."
        ) from e
    return RawSink


def _to_numpy(obj: Any) -> Any:
    """Converts a pandas `Series`/`DataFrame` to a numpy array via its own
    `.to_numpy()`; anything else (already a numpy `ndarray`, or any other
    row-iterable whose rows themselves support `.tobytes()`) is passed
    through unchanged. `RawSink` duck-types its auto-detect-format step on
    `type(x).__name__` containing `"ndarray"` (see `kafkaml_datasources.
    sink.KafkaMLSink.__shape_to_string`/`__type_to_string`) - a real numpy
    array has to reach it unwrapped, not merely something array-*like*."""
    to_numpy = getattr(obj, "to_numpy", None)
    if callable(to_numpy):
        return to_numpy()
    return obj


def send_dataset(
    bootstrap_servers: str,
    topic: str,
    deployment_id: int,
    data: Any,
    labels: Any,
    *,
    description: str = "",
    validation_rate: float = 0.0,
    test_rate: float = 0.0,
    control_topic: str = "KAFKA_ML_CONTROL_TOPIC",
    group_id: str = "sink",
) -> None:
    """Sends a `data`/`labels` dataset pair to Kafka and registers it as a
    Kafka-ML datasource for `deployment_id` - the flow every
    `examples/*/*_dataset_training_example.py` script hand-rolls with
    `kafkaml_datasources.RawSink` directly, as one call.

    `data`/`labels` each accept a numpy `ndarray`, a pandas `Series`/
    `DataFrame` (converted via `.to_numpy()`), or anything else already
    shaped like one of those (row-iterable, each row supporting
    `.tobytes()` - what `RawSink.send()` itself requires). Both must have
    the same length; row `i` of `data` is paired with row `i` of
    `labels`, same as the parallel-iteration pattern the examples use
    (``for x, y in zip(x_train, y_train): sink.send(data=x, label=y)``).
    Data/label dtype and shape are auto-detected from the first row, same
    as a hand-written `RawSink` caller gets by leaving `data_type`/
    `data_reshape` unset.

    Registration happens automatically when the underlying `RawSink` is
    closed - there's no separate REST call to make, which is why this
    function takes Kafka connection details directly rather than a
    `KafkaMLClient` instance (`deployment_id` still has to come from an
    earlier `KafkaMLClient.create_deployment()` call, same as every
    example script gets it from the deployment it already made via the
    frontend/API).

    Raises `ValueError` if `data` and `labels` have different lengths -
    checked up front rather than left to raise confusingly mid-stream
    (or worse, silently truncate via `zip`) partway through a real send.
    """
    RawSink = _import_raw_sink()

    data = _to_numpy(data)
    labels = _to_numpy(labels)
    if len(data) != len(labels):
        raise ValueError(f"data and labels must have the same length, got {len(data)} and {len(labels)}")

    sink = RawSink(
        boostrap_servers=bootstrap_servers,
        topic=topic,
        deployment_id=deployment_id,
        description=description,
        validation_rate=validation_rate,
        test_rate=test_rate,
        control_topic=control_topic,
        group_id=group_id,
    )
    try:
        for x, y in zip(data, labels):
            sink.send(data=x, label=y)
    finally:
        # RawSink.close() is what actually registers the datasource (the
        # control-topic message) - always send it, even if a mid-stream
        # send() raised, so a partial send still gets registered with
        # whatever total_msg it actually reached rather than silently
        # leaving the topic's data unregistered and orphaned.
        sink.close()


def send_dataframe(
    bootstrap_servers: str,
    topic: str,
    deployment_id: int,
    dataframe: Any,
    label_column: str,
    *,
    description: str = "",
    validation_rate: float = 0.0,
    test_rate: float = 0.0,
    control_topic: str = "KAFKA_ML_CONTROL_TOPIC",
    group_id: str = "sink",
) -> None:
    """Convenience wrapper over `send_dataset` for a single pandas
    `DataFrame` holding both features and label in one table - splits
    `label_column` off as the label dataset, sends every other column as
    the (row-vector) data dataset. See `send_dataset` for the rest of the
    behavior (auto format detection, validation/test split, etc.)."""
    labels = dataframe[label_column]
    data = dataframe.drop(columns=[label_column])
    send_dataset(
        bootstrap_servers,
        topic,
        deployment_id,
        data,
        labels,
        description=description,
        validation_rate=validation_rate,
        test_rate=test_rate,
        control_topic=control_topic,
        group_id=group_id,
    )
