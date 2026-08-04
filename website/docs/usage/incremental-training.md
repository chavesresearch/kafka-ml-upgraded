---
sidebar_position: 4
---

# Incremental Training

Incremental training continuously extends an existing model's knowledge
as new data arrives, instead of retraining from a fixed dataset — useful
when data becomes available gradually over time, or is too large to fit
in memory at once.

Currently only TensorFlow supports incremental training. The setup is
the same as [Single Models](./single-models), with extra deployment
fields depending on which of the two incremental modes you use.

## Time-limited

- **`stream_timeout`** — how long (ms) the dataset waits for new messages
  before timing out. Defaults to `60000`.

![Deploy a time-limited incremental configuration](/img/docs/deploy-incremental-configuration-1.png)

## Indefinite

- **`monitoring_metric`** — which validation-phase metric to track (required).
- **`direction`** — which direction counts as "improving" for that metric (required).
- **`improvement`** — the threshold that triggers an automatic inference
  deployment. Defaults to `0.05`.

![Deploy an indefinite incremental configuration](/img/docs/deploy-incremental-configuration-2.png)

Once deployed, one training result appears per model, ready to receive
stream data. If you used the MNIST model, run:

```sh
python examples/MNIST_RAW_format/mnist_dataset_online_training_example.py
```
