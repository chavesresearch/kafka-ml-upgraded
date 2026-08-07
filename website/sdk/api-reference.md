---
sidebar_position: 6
---

# API Reference

Every public method on `KafkaMLClient`. Every list/get method returns
plain `dict`/`list[dict]` straight from the JSON response — there are no
typed response models yet (see the [Introduction](./intro)'s Status
note).

## Constructing a client

### `KafkaMLClient(base_url, timeout=30)`

Opens an `httpx.Client` against the backend's base URL (e.g.
`"http://localhost:8000"`). `timeout` is the per-request timeout in
seconds.

### `close()`

Closes the underlying HTTP connection pool. Not needed if you use the
client as a context manager (`with KafkaMLClient(...) as client:`).

## Models

| Method | Returns | Notes |
|---|---|---|
| `create_model(name, code, framework="tf", imports="", description="", distributed=False, father=None)` | `int` | New model id. `father` links a distributed child to its parent's model id. |
| `get_model(model_id)` | `dict` | One model. |
| `list_models()` | `list[dict]` | Every model. |
| `delete_model(model_id)` | `None` | |

## Configurations

| Method | Returns | Notes |
|---|---|---|
| `create_configuration(name, model_ids, description="")` | `int` | New configuration id. For a distributed model, pass only the root model's id. |
| `get_configuration(configuration_id)` | `dict` | |
| `list_configurations()` | `list[dict]` | |
| `delete_configuration(configuration_id)` | `None` | |

## Deployments

| Method | Returns | Notes |
|---|---|---|
| `create_deployment(configuration, batch=1, **fields)` | `int` | Submits real Kubernetes training Job(s). See [Deployments & Training Modes](./deployments-and-training-modes) for the full `**fields` reference. |
| `list_deployments()` | `list[dict]` | |
| `delete_deployment(deployment_id)` | `None` | |

## Datasets

Needs the `datasets` extra (`pip install kafkaml-client[datasets]`). See
[Sending Datasets](./sending-datasets) for the full explanation.

| Method | Returns | Notes |
|---|---|---|
| `send_dataset(bootstrap_servers, topic, deployment_id, data, labels, *, description="", validation_rate=0.0, test_rate=0.0, control_topic="KAFKA_ML_CONTROL_TOPIC", group_id="sink")` | `None` | `data`/`labels` accept a numpy `ndarray` or a pandas `Series`/`DataFrame`. Registers the datasource automatically. Raises `ValueError` if `data`/`labels` have different lengths. |
| `send_dataframe(bootstrap_servers, topic, deployment_id, dataframe, label_column, **kwargs)` | `None` | Convenience wrapper for a single `DataFrame` holding both features and label; splits `label_column` off and calls `send_dataset`. Same `**kwargs` as `send_dataset`. |

## Results

| Method | Returns | Notes |
|---|---|---|
| `list_results(deployment_id=None)` | `list[dict]` | Optionally filtered to one deployment. |
| `get_result(result_id)` | `dict` | Raises `KafkaMLError` (`status_code=404`) if not found. |
| `wait_for_results(deployment_id, status="finished", timeout=120, poll_interval=2, min_results=1)` | `list[dict]` | Raises **`TimeoutError`** (not `KafkaMLError`) if `status` isn't reached in time. |

## Inference

| Method | Returns | Notes |
|---|---|---|
| `deploy_inference(result_id, input_topic, output_topic, input_format="RAW", input_config="", replicas=1, **fields)` | `int` | Creates a real, long-running `ReplicationController`. |
| `list_inferences()` | `list[dict]` | |
| `stop_inference(inference_id)` | `None` | Stops a running inference. |
| `delete_inference(inference_id)` | `None` | |
| `predict_one(bootstrap_servers, input_topic, output_topic, row, *, timeout_ms=60000, group_id="kafkaml-client")` | `dict` | Needs the `datasets` extra. Sends one row, returns its prediction. Output consumer always reads from `"earliest"`. |
| `predict_batch(bootstrap_servers, input_topic, output_topic, rows, **kwargs)` | `list[dict]` | Needs the `datasets` extra. Sends every row, returns predictions in send order. Raises `TimeoutError` if fewer predictions arrive than rows sent. |

## Errors

### `KafkaMLError(RuntimeError)`

Raised whenever a request to the backend returns an HTTP error status.
Carries:

- `.status_code: int` — the HTTP status code
- `.response_text: str` — the raw response body

Note that `wait_for_results` raises Python's built-in `TimeoutError`
instead, since a timeout is a client-side wait condition, not something
the backend returned an error status for.
