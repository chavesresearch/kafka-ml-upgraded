# Kustomize for Kafka-ML Federated Module

This folder contains multiple Kustomize files to ease the deployment on
Kubernetes. Notably the following versions are available:

| Version      | Resource URL                                                               |
| ------------ | ---------------------------------------------------------                  |
| `master`     | `github.com/ertis-research/kafka-ml/federated-module/kustomize/master`     |
| `master-gpu` | `github.com/ertis-research/kafka-ml/federated-module/kustomize/master-gpu` |
| `v1.1`       | `github.com/ertis-research/kafka-ml/federated-module/kustomize/v1.1`       |
| `v1.1-gpu`   | `github.com/ertis-research/kafka-ml/federated-module/kustomize/v1.1-gpu`   |
| `v2.0`       | `github.com/ertis-research/kafka-ml/federated-module/kustomize/v2.0`       |
| `v2.0-gpu`   | `github.com/ertis-research/kafka-ml/federated-module/kustomize/v2.0-gpu`   |
| `local`      | `github.com/ertis-research/kafka-ml/federated-module/kustomize/local`      |

These versions should work with any Kubernetes compatible cluster, such as K8s
and K3s. There was never a versioned overlay between `v1.1` and `v2.0` in
this module (the main module has `v1.0`/`v1.3` in between - this module's
`federated_backend` didn't exist as a separately-versioned release until
now) - `v2.0` is the reworked release, see `../../kustomize/README.md`'s
`v2.0` note for what changed. `federated_backend` itself went
Django→Litestar as part of this rework (see
`../CLAUDE.md`'s "federated_backend/ — Django→Litestar rewrite" section)
with **zero** resource-shape changes, so `base` (and every overlay below)
needed no changes for it either.

## Installation

1. Create a `kustomize.yaml` file with the following contents:

```yaml
resources:
  # Choose your kustomize version
  - github.com/ertis-research/kafka-ml/federated-module/kustomize/master

# Namespace where Kafka-ML will be deployed
namespace: kafkaml

configMapGenerator:
  - name: federated-kafkaml-configmap
    behavior: merge
    literals:
      # Comma separated list of Kafka brokers
      - brokers=kafka1,kafka2,kafka3
```

2. Deploy using the following command

```sh
# Create the namespace first if it doesn't exists
kubectl create namespace kafkaml
kubectl apply -k .
```

## Configuration options

You can modify the `kafkaml-configmap` resource to customize the installation.
The available keys are:

| Key                                     | Description                                         | Default value               |
| --------------------------------------- | --------------------------------------------------- | --------------------------- |
| `federated.backend.url`                 | Backend's URL                                       | federated-backend:8085      |
| `backend.allowedhosts`                  | Configures the `Allowed-Hosts` header of backend    | 127.0.0.1,localhost,backend |
| `federated.tensorflow.training.image`   | Container image used for Fed TensorFlow training    | \*                          |
| `federated.pytorch.training.image`      | Container image used for Fed PyTorch training       | \*                          |
| `kml.cloud.brokers`                     | Comma separated list of Kafka-ML Cloud brokers      | -                           |
| `federated.data.brokers`                | Comma separated list of Kafka-ML Federated brokers  | -                           |
| `debug`                                 | Enable debug mode. Possible values: `[0,1]`         | -                           |

> \* value depends on the kustomize version used. See
> [Kustomize for Kafka-ML](#kustomize-for-kafka-ml)
