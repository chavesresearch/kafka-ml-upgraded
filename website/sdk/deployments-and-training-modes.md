---
sidebar_position: 3
---

# Deployments & Training Modes

`create_deployment` is the call that makes the backend submit a real
Kubernetes training Job — one per root model in the configuration:

```python
deployment_id = client.create_deployment(
    configuration=config_id,
    batch=4,
    **fields,
)
```

`**fields` is passed straight through to the API. Whether a model is
**distributed** is set when the model itself is created
(`create_model(..., distributed=True)`, see [Creating
Models](./creating-models)); everything else below is a deployment-level
flag. Combining `distributed` (model-level) with `incremental`/
`federated`/`blockchain` (deployment-level) is exactly how Kafka-ML's 9
training modes are produced — see the [Interactive
Showcase](/showcase) for an animated walkthrough of each.

## Every field `create_deployment` accepts

| Field | Applies to | Notes |
|---|---|---|
| `tf_kwargs_fit`, `tf_kwargs_val` | TensorFlow | `"key=value, key2=value2"` string, passed to `model.fit`/`.evaluate` |
| `pth_kwargs_fit`, `pth_kwargs_val` | PyTorch | Same string format, different keys (e.g. `"max_epochs=1"`, ignite's trainer-run kwargs) |
| `incremental` | Incremental modes | `True` enables streaming/incremental training |
| `indefinite` | Incremental | `True` for an open-ended run instead of a fixed stream timeout |
| `stream_timeout` | Incremental, time-limited | ms to wait for new data before finishing |
| `monitoring_metric`, `change`, `improvement` | Incremental, indefinite | which metric to track, which direction is "improving", and the threshold that triggers an automatic inference deployment |
| `optimizer`, `learning_rate`, `loss`, `metrics` | Distributed models | optional, default to `adam`/`0.001`/`sparse_categorical_crossentropy`/`sparse_categorical_accuracy` |
| `federated` | Federated modes | `True` enables federated learning |
| `agg_rounds` | Federated | number of train+aggregate rounds |
| `min_data` | Federated | minimum data volume a device needs to join a round |
| `agg_strategy` | Federated | aggregation strategy - currently only `"FedAvg"` |
| `data_restriction` | Federated | dict describing the data pattern (shape, labels, etc.) a device's data must match |
| `blockchain` | Federated | `True` coordinates the round on-chain and enables real ERC-20 reward payouts (CASE 9 - see the [Showcase](/showcase?case=9)) |
| `unsupervised`, `unsupervised_rounds`, `confidence` | Semi-supervised | orthogonal to the CASE dispatch below - see [Semi-Supervised Learning](/docs/usage/semi-supervised-learning) |
| `conf_mat_settings` | Any | enable confusion-matrix generation |
| `gpumem` | Any | GPU memory estimate; leave at `0` if your GPU(s) aren't tuned |

## Which combination produces which training mode

| `distributed` (model) | `incremental` | `federated` | `blockchain` | Mode |
|---|---|---|---|---|
| ☐ | ☐ | ☐ | ☐ | Single, classic |
| ☐ | ✅ | ☐ | ☐ | Single, incremental |
| ✅ | ☐ | ☐ | ☐ | Distributed |
| ✅ | ✅ | ☐ | ☐ | Distributed + incremental |
| ☐ | ☐ | ✅ | ☐ | Federated |
| ☐ | ✅ | ✅ | ☐ | Federated + incremental |
| ✅ | ☐ | ✅ | ☐ | Federated + distributed |
| ✅ | ✅ | ✅ | ☐ | Federated + distributed + incremental |
| ☐ | ☐ | ✅ | ✅ | Federated + blockchain |

## Example: a federated deployment

```python
deployment_id = client.create_deployment(
    configuration=config_id,
    batch=4,
    tf_kwargs_fit="epochs=1",
    federated=True,
    agg_rounds=5,
    min_data=100,
    agg_strategy="FedAvg",
    data_restriction={},
)
```
