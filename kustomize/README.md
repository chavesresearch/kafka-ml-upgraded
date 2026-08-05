# Kustomize for Kafka-ML

This folder contains multiple Kustomize files to ease the deployment on
Kubernetes. Notably the following versions are available:

| Version             | Resource URL                                                     |
| ------------------- | ---------------------------------------------------------------- |
| `master`            | `github.com/ertis-research/kafka-ml/kustomize/master`            |
| `master-gpu`        | `github.com/ertis-research/kafka-ml/kustomize/master-gpu`        |
| `v1.0`              | `github.com/ertis-research/kafka-ml/kustomize/v1.0`              |
| `v1.0-gpu`          | `github.com/ertis-research/kafka-ml/kustomize/v1.0-gpu`          |
| `v1.1`              | `github.com/ertis-research/kafka-ml/kustomize/v1.1`              |
| `v1.1-gpu`          | `github.com/ertis-research/kafka-ml/kustomize/v1.1-gpu`          |
| `v1.3`              | `github.com/ertis-research/kafka-ml/kustomize/v1.3`              |
| `v1.3-gpu`          | `github.com/ertis-research/kafka-ml/kustomize/v1.3-gpu`          |
| `v2.0`              | `github.com/ertis-research/kafka-ml/kustomize/v2.0`              |
| `v2.0-gpu`          | `github.com/ertis-research/kafka-ml/kustomize/v2.0-gpu`          |
| `local`             | `github.com/ertis-research/kafka-ml/kustomize/local`             |

These versions should work with any Kubernetes compatible cluster, such as K8s
and K3s. (This table used to also list `v1.1-gpu-nvidia`, a directory that no
longer exists - and was silently missing `v1.3`/`v1.3-gpu`, which do. Fixed
2026-08-04; if you're pinned to `v1.1-gpu-nvidia` from an old install, use
`v1.1-gpu` instead - GPU scheduling here has only ever meant "swap to a
CUDA-enabled image tag", see the note below, so there was nothing
NVIDIA-specific to lose.)

`v2.0` is the reworked release: React 19 frontend (was Angular/Vue),
Litestar/SQLAlchemy async backend and federated backend (both were
Django/DRF), modernized `model_training`/`model_inference`/
`mlcode_executor`/`datasources` dependency stacks, `web3` 7.x (was 5.x).
See the repo root README/`FUTURE.md` for the full list of what changed -
`kustomize/base` itself needed **zero** changes for this rework, since it
changed the deployed services' internals, not the Kubernetes resource
shapes those services run in.

### A note on GPU support and version staleness

Each `{version}-gpu` overlay (`master-gpu`, `v1.0-gpu`, `v1.1-gpu`,
`v1.3-gpu`, `v2.0-gpu`) only swaps in `-gpu`-suffixed image tags (via
`kustomize/components/gpu-executor-images`, a single shared Kustomize
Component every `{version}-gpu` overlay references - not duplicated
per-version) - it does **not** encode any GPU device-plugin/scheduler
config (no `nodeSelector`, no `nvidia.com/gpu` resource requests). That's
entirely on the operator to set up cluster-side - see the root README's
"GPU configuration" section. This means there's no "GPU scheduling
plugin migration" for these overlays to have drifted out of sync on -
every version's `-gpu` variant does the same one thing (image tag swap),
verified identical across all 4 pre-existing overlays with a real
`kubectl kustomize` diff before and after extracting the shared
component (2026-08-04); `v2.0-gpu` (2026-08-05) reuses that same
component unchanged, verified the same way against `v1.3-gpu`.

## Installation

1. Create a `kustomize.yaml` file with the following contents:

```yaml
resources:
  # Choose your kustomize version
  - github.com/ertis-research/kafka-ml/kustomize/master

# Namespace where Kafka-ML will be deployed
namespace: kafkaml

configMapGenerator:
  - name: kafkaml-configmap
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

| Key                          | Description                                      | Default value                 |
| ---------------------------- | ------------------------------------------------ | ----------------------------- |
| `control.topic`              | Control topic name                               | KAFKA_ML_CONTROL_TOPIC        |
| `frontend.url`               | Frontend's URL                                   | http://localhost              |
| `backend.url`                | Backend's URL                                    | http://backend:8000           |
| `backend.address`            | Backend's address and port                       | backend:8000                  |
| `backend.allowedhosts`       | Configures the `Allowed-Hosts` header of backend | 127.0.0.1,localhost,backend   |
| `tfexecutor.url`             | TensorFlow executor's URL                        | http://tfexecutor:8001/       |
| `pthexecutor.url`            | PyTorch executor's URL                           | http://pthexecutor:8002/      |
| `federated.modelloggertopic` | Topic used for model logging in Kafka-ML Fed     | FEDERATED_MODEL_CONTROL_TOPIC |
| `tensorflow.training.image`  | Container image used for TensorFlow training     | \*                            |
| `tensorflow.inference.image` | Container image used for TensorFlow inference    | \*                            |
| `pytorch.training.image`     | Container image used for PyTorch training        | \*                            |
| `pytorch.inference.image`    | Container image used for PyTorch inference       | \*                            |
| `brokers`                    | Comma separated list of Kafka brokers            | -                             |
| `debug`                      | Enable debug mode. Possible values: `[0,1]`      | -                             |

> \* value depends on the kustomize version used. See
> [Kustomize for Kafka-ML](#kustomize-for-kafka-ml)
