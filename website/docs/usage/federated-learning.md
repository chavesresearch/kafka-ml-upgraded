---
sidebar_position: 5
---

# Federated Learning

Federated learning trains collaboratively across decentralized devices
without moving their raw data anywhere. Each device trains locally on
its own data and shares only model updates (weights/gradients); a
central aggregator combines those updates into an improved global model,
which is sent back out for another round. This preserves data privacy
and avoids large-scale data transfers — well suited to mobile devices,
healthcare systems, and IoT networks.

Currently only TensorFlow supports federated learning. The setup is the
same as [Single Models](./single-models), with four extra deployment
fields:

- **`aggregation_rounds`** — how many rounds to run (train on devices,
  then aggregate) before finishing.
- **`minimun_data`** — the minimum amount of data a device must have to
  join a round.
- **`data_restriction`** — the data pattern (input shape, labels, etc.)
  a device's data must match to join.
- **aggregation strategy** — how updates get combined. Currently only
  the averaging strategy (FedAvg) is available.

![Deploy a federated configuration](/img/docs/deploy-federated-configuration.png)

Once deployed, the model is ready to be sent to devices for training.
Any device whose data matches the requirements trains locally and sends
its weights back for aggregation; once aggregation finishes, the updated
model goes back out for another round. This repeats until
`aggregation_rounds` is reached.

If you used the MNIST model, run:

```sh
python examples/FEDERATED_MNIST_RAW_format/mnist_dataset_federated_training_example.py
```

## Distributed, incremental, and blockchain-traced variants

Federated learning composes with the other training modes: a federated
model can also be distributed (a father/child submodel chain trained
federatively) or incremental (a continuous streaming federated round),
and a federated round can optionally be coordinated on-chain with real
ERC-20 token rewards paid out to participating devices by contribution —
see [Blockchain-Traced Training](./blockchain-traced-training) for the
operational how-to (chain setup, wallet Secret, enabling it) once you're
ready to actually run it, not just watch it.

The [Interactive Showcase](/showcase) covers every combination
(9 modes total) with an animated walkthrough of each — a good next stop
if you want to see how these variants differ before configuring one for
real.
