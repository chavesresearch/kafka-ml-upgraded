---
sidebar_position: 5
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

## Errors

### `KafkaMLError(RuntimeError)`

Raised whenever a request to the backend returns an HTTP error status.
Carries:

- `.status_code: int` — the HTTP status code
- `.response_text: str` — the raw response body

Note that `wait_for_results` raises Python's built-in `TimeoutError`
instead, since a timeout is a client-side wait condition, not something
the backend returned an error status for.
