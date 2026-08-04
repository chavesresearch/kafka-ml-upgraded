---
sidebar_position: 3
---

# Semi-Supervised Learning

Semi-supervised learning sits between supervised and unsupervised
learning: the model trains on a dataset containing both labeled and
unlabeled examples, using the small labeled portion to guide learning
while the much larger unlabeled portion improves performance further.

Currently only TensorFlow supports semi-supervised training. The setup
is the same as [Single Models](./single-models), except the deployment
form gains two extra fields:

- **`unsupervised_rounds`** — how many rounds to iterate over the
  unlabeled data. Defaults to `5`.
- **`confidence`** — the minimum prediction confidence required before an
  unlabeled example is assigned that label. Defaults to `0.9`.

Neither is required.

![Deploy a semi-supervised configuration](/img/docs/deploy-unsupervised-configuration.png)

Once deployed, one training result appears per model, ready to receive
stream data. If you used the MNIST model, run:

```sh
python examples/MNIST_RAW_format/mnist_dataset_unsupervised_training_example.py
```
