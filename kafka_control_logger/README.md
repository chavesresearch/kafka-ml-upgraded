# Kafka Control Logger

This module contains the Kafka control logger that consumes control Kafka-ML messages to send them to the Back-end, so it can persist a record of every datasource submitted. That's all - it does not filter by deployment id (unlike per-deployment consumers such as `mlcode_executor`/`model_training`), since its job is to archive every datasource submission, not just the ones relevant to a specific task.

A brief introduction of its files:
- File `logger.py` main file of this module.

## Installation for local development

Dependencies are managed with [uv](https://docs.astral.sh/uv/) - `pyproject.toml` + `uv.lock`, no `requirements.txt`.

Run `uv sync` to install the dependencies used by this module.

Once installed, you have to set each one of the environment vars below to execute this task. For instance, you can run `export CONTROL_TOPIC=control` to export the `CONTROL_TOPIC` var with the value `control`. Once configured all the vars, execute `uv run logger.py` to execute this task.

## Fixed since the original version

- **Broken timestamp**: the `time` field sent to the backend used
  `datetime.utcfromtimestamp(...).strftime("%Y-%m-%dT%H:%M:%S%Z")` - `%Z`
  renders as an empty string for a naive datetime (which
  `utcfromtimestamp()` always returns), so every submission silently sent a
  timestamp with no timezone marker at all. Now built with
  `datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()`, which the
  backend parses with `datetime.fromisoformat()` - see
  `backend/CLAUDE.md` for the matching fix on that side (passing
  the raw string straight into the DB model was its own separate bug).
- **Retry-exhaustion silently dropped messages**: on success, the old code
  called a bare `consumer.commit()`, which commits the consumer's *current*
  position. If a message exhausted all `RETRIES` attempts, it was never
  itself committed - but the next unrelated message's successful commit
  would still sweep its offset forward, silently dropping it with no error,
  no crash, no redelivery. Fixed two ways together: (1) a message that
  exhausts retries now raises `BackendUnreachableError`, which propagates
  out of the consume loop and exits the process (`sys.exit(1)`) instead of
  continuing to the next message - Kafka never advances past it, so a pod
  restart redelivers it from the last real success; (2) successful sends
  now commit that specific message's offset explicitly
  (`TopicPartition`/`OffsetAndMetadata`), not a bare position-based commit.
- `urlopen()` had no timeout, so a hung backend connection could block
  indefinitely; added `REQUEST_TIMEOUT = 30`.
- `kafka-python` bumped `2.0.2` → `3.0.9` (actively maintained again -
  don't assume otherwise without checking PyPI first) and the base image
  from `python:3.8.6` (EOL) to `python:3.12-slim`.

## Environments vars received

- **BOOTSTRAP_SERVERS**: list of brokers for the connection to Apache Kafka.
- **BACKEND**: hostname and port of the Back-end (e.g., localhost:8000).
- **CONTROL_TOPIC**: name of the Kafka control topic.