---
sidebar_position: 2
---

# Creating Models

## A single model

```python
model_id = client.create_model(
    name="my-model",
    code=MODEL_CODE,
    framework="tf",       # or "pth" for PyTorch
    imports="",           # extra import statements the code needs
    description="",
    distributed=False,
)
```

`code` is validated live by the matching `mlcode_executor` service before
it's persisted — a `KafkaMLError` with `status_code == 400` means the
code itself didn't pass that check, not a transport problem.

Since the backend's `POST /models/` doesn't return the created object
(no `Location` header, empty `201` body), `create_model` looks the new
model up by name right after creating it and returns its id — so model
names must be unique.

## Distributed models

A distributed model is a father/child chain of sub-models. Create each
node separately, passing `father` for every non-root node:

```python
cloud_id = client.create_model("cloud-model", CLOUD_MODEL_CODE, distributed=True)
edge_id = client.create_model("edge-model", EDGE_MODEL_CODE, distributed=True, father=cloud_id)
```

When building the configuration, pass only the **root** (father-less)
model's id — the backend walks the chain and pulls in every child
automatically:

```python
config_id = client.create_configuration("my-config", [cloud_id])
```

See the [Distributed Models](/docs/usage/distributed-models) guide for
what the model code itself needs to look like (each sub-model's inputs/
outputs have to line up with its position in the chain), and the
[Interactive Showcase](/showcase) for an animated walkthrough of how a
distributed training round actually runs.

## Configurations

A configuration groups one or more models to train together — useful
for comparing several models against the same data stream, or just to
give a single model (or distributed chain) somewhere to attach a
deployment to:

```python
config_id = client.create_configuration(
    name="my-config",
    model_ids=[model_id],
    description="",
)
```
