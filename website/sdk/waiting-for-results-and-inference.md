---
sidebar_position: 5
---

# Waiting for Results & Inference

## Polling for a finished result

```python
results = client.wait_for_results(
    deployment_id,
    status="finished",
    timeout=120,
    poll_interval=2,
    min_results=1,
)
```

Polls `/results/` until every training result for `deployment_id` reaches
`status` (default `"finished"`), or raises **`TimeoutError`** — not
`KafkaMLError` — once `timeout` seconds elapse. A distributed deployment
produces one result per submodel, so set `min_results` to match how many
submodels are in the chain.

## Real-time inference

```python
inference_id = client.deploy_inference(
    result_id=results[0]["id"],
    input_topic="my-input",
    output_topic="my-output",
    input_format="RAW",
    replicas=1,
)
```

This creates a real Kubernetes `ReplicationController` — long-running,
not a Job — so remember to clean it up when you're done:

```python
client.stop_inference(inference_id)
client.delete_inference(inference_id)
```

Input-stream parameters (`input_format`/`input_config`) default to
whatever was seen during training and usually don't need overriding.

### Sending requests and reading predictions

Needs the [`datasets` extra](./sending-datasets). `predict_one` sends
one row to the input topic and returns the one prediction read back;
`predict_batch` does the same for several rows at once, returning
predictions in send order:

```python
prediction = client.predict_one("localhost:9094", "my-input", "my-output", X[0])
predictions = client.predict_batch("localhost:9094", "my-input", "my-output", X[:5])
```

Both accept a numpy `ndarray` row (or a pandas `Series`/`DataFrame` row).
`predict_batch` raises `TimeoutError` if fewer predictions arrive than
rows were sent within `timeout_ms` (default 60s).

## Listing and inspecting results

```python
client.list_results()                      # every result
client.list_results(deployment_id=5)       # just one deployment's
client.get_result(result_id=42)            # one result by id
```

`get_result` is client-side filtering over `list_results()` — there's no
single-result `GET` endpoint on the backend.
