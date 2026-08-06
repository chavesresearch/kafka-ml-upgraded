---
sidebar_position: 11
---

# kustomize

`kustomize/` holds the Kubernetes manifests used to deploy Kafka-ML with
[Kustomize](https://kustomize.io/), as an alternative to applying the
raw per-file manifests shown in [Single-Node
Deployment](../installation/single-node) and [Distributed Cluster
Deployment](../installation/distributed-cluster). This page is about how
the overlay tree is organized internally and how to extend it — for how
to actually deploy with it, see `kustomize/README.md`'s Installation
section.

## Directory shape

```
kustomize/
  base/                    # shared resource definitions, referenced by every overlay
    resources/
    kustomization.yaml
  components/
    gpu-executor-images/   # a reusable Kustomize Component, not a full overlay
  local/                   # single-node dev overlay (Docker Desktop / minikube)
  master/, master-gpu/     # tracks the default branch
  v1.0/, v1.0-gpu/
  v1.1/, v1.1-gpu/
  v1.3/, v1.3-gpu/
  v2.0/, v2.0-gpu/         # current release
```

Every version overlay (`local`, `master`, `v1.0`, `v1.1`, `v1.3`, `v2.0`)
is a real, independent directory — none of them are generated. Each
`{version}-gpu` overlay layers on top of its non-GPU counterpart rather
than duplicating it.

## `base`

`base/kustomization.yaml` lists the core resources every deployment
needs, all under `base/resources/`:

- `role.yaml` — a `ServiceAccount` (`kafkaml`), a `Role`
  (`kafkaml-role`) granting `create/get/list/delete/watch` on
  `deployments`, `jobs`, `pods`, `replicasets`, `services`, and
  `replicationcontrollers` in the `""`/`apps`/`batch` API groups, and a
  `RoleBinding` tying them together — this is what lets `backend`
  dynamically create the training/inference Jobs and Deployments
  described in the [backend](./backend) page.
- `kafkaml-configmap.yaml` — the `kafkaml-configmap` ConfigMap that every
  overlay's `configMapGenerator` merges into (brokers, control topic,
  service URLs, executor/training/inference image names — see the keys
  documented in `kustomize/README.md`'s Configuration options table).
- `backend-deployment.yaml` / `backend-service.yaml`
- `frontend-deployment.yaml` / `frontend-service.yaml`
- `kafka-control-logger-deployment.yaml`
- `tf-executor-deployment.yaml` / `tf-executor-service.yaml`
- `pth-executor-deployment.yaml` / `pth-executor-service.yaml`
- `networkpolicies.yaml`

`base` does **not** include Kafka itself, blockchain infrastructure, or a
namespace — those are added by specific overlays (see `local` below) or
left to the operator, since a real deployment typically points at an
existing Kafka cluster rather than one Kustomize should own.

Notably, `base` needed **zero** changes for the v2.0 rework (React 19
frontend replacing Angular/Vue, Litestar/SQLAlchemy async backend and
federated backend replacing Django/DRF, modernized
`model_training`/`model_inference`/`mlcode_executor`/`datasources`
dependency stacks, `web3` 7.x replacing 5.x) — that rework changed the
deployed services' internals, not the Kubernetes resource shapes those
services run in, so every overlay could keep referencing the same
`base` unchanged.

## How a version overlay patches `base`

A typical version overlay (e.g. `v2.0/kustomization.yaml`) does three
things on top of `resources: ["../base"]`:

1. **`configMapGenerator` with `behavior: merge`** — adds the
   version-specific training/inference image names
   (`tensorflow.training.image`, `tensorflow.inference.image`,
   `pytorch.training.image`, `pytorch.inference.image`) into the shared
   `kafkaml-configmap` without redefining the whole ConfigMap.
2. **`images:`** — an image transformer that rewrites the placeholder
   image names baked into `base`'s Deployments (`kafka-ml-backend`,
   `kafka-ml-frontend`, `kafka-ml-kafka_control_logger`,
   `kafka-ml-pthexecutor`, `kafka-ml-tfexecutor`) to a real registry name
   and version tag, e.g. `ertis/kafka-ml-backend:v2.0`.
3. Nothing else, in the plain (non-GPU, non-local) case — replica counts
   and resource requests are left at whatever `base`'s Deployments
   already specify.

Each `{version}-gpu` overlay (e.g. `v2.0-gpu/kustomization.yaml`) layers
on top of its own version overlay (`resources: ["../v2.0"]`) rather than
`base` directly, adds the shared `components/gpu-executor-images`
Component, and merges in `-gpu`-suffixed training/inference image names
via its own `configMapGenerator`. `components/gpu-executor-images` is a
single Kustomize `Component` (`apiVersion:
kustomize.config.k8s.io/v1alpha1`, `kind: Component`) referenced by
every `{version}-gpu` overlay instead of being copy-pasted into each
one — it renames the two executor images
(`ertis/kafka-ml-pthexecutor` → `ertis/kafka-ml-pthexecutor-gpu`,
`ertis/kafka-ml-tfexecutor` → `ertis/kafka-ml-tfexecutor-gpu`) and
deliberately does **not** set an image tag, so it composes correctly on
top of whatever tag the version overlay it's layered onto already
applied.

GPU support here is scoped narrowly: swapping in `-gpu`-suffixed image
tags for the code-executor services is *all* a `{version}-gpu` overlay
does. It does not encode any device-plugin or scheduler configuration —
no `nodeSelector`, no `nvidia.com/gpu` resource requests. That's left
entirely to the operator's cluster setup (see the root README's GPU
configuration section, and [GPU
Configuration](../installation/gpu-configuration)).

## The `local` overlay

`local/kustomization.yaml` is the shape a contributor would follow for
"deploy everything, self-contained, for local development." It differs
from the tagged version overlays in a few ways worth noting if adding a
new overlay:

- It adds its own extra resources under `local/resources/`
  (`namespace.yaml`, `kafka-deployment.yaml`, `kafka-service.yaml`,
  `blockchain-devnet.yaml`, `blockchain-wallet-secret.yaml`) alongside
  layering on `../v1.0` — a self-contained Kafka broker and a local Anvil
  blockchain devnet (for CASE=9, blockchain-traced federated learning)
  aren't part of `base` or any tagged overlay, since a real deployment
  usually points at existing infrastructure instead.
- It sets `namespace: kafkaml` directly, rather than expecting the
  consumer's own top-level `kustomize.yaml` to set it (compare the
  `README.md` Installation example, which sets `namespace: kafkaml` in a
  wrapper file that references a version overlay as a remote resource).
- Its `images:` block remaps images a second time, matching against the
  *already-renamed* names the underlying `../v1.0` overlay produced
  (e.g. matching `ertis/kafka-ml-backend`, not the raw `base` placeholder
  `kafka-ml-backend`) — Kustomize's image transformer matches against the
  current name in the resource tree, not the original base name, so a
  second layer of renaming has to target the first layer's output.
- It adds explicit JSON6902 `patches:` forcing `imagePullPolicy:
  IfNotPresent` on the backend/frontend/kafka-control-logger/tfexecutor/
  pthexecutor Deployments, overriding `base`'s default
  `imagePullPolicy: Always` — necessary because these are locally-built
  images living only in the local Docker daemon's image cache (Docker
  Desktop's Kubernetes shares that cache), not published to any
  registry, so `Always` would try and fail to pull them remotely.

## Statically defined vs. dynamically created resources

Everything under `kustomize/` is **static, pre-deployment** infrastructure
— it exists before Kafka-ML runs and stays running (backend, frontend,
Kafka, the code executors, RBAC). It does not include the Kubernetes
`Job`/`Deployment`/`ReplicationController` objects that actually run
model training and inference — those are built dynamically, per
request, by [backend](./backend)'s `app/job_manifest_generator.py` and
submitted through `kubernetes_asyncio`, and by
`federated-module`'s `federated_backend/app/kubernetes_deploy.py`
(`deploy_on_kubernetes`) for edge-device training Jobs. The `role.yaml`
RBAC resources in `base` are exactly what authorizes those two code
paths to create/list/delete those objects at runtime — the static
overlay tree provisions the permission, the Python code provisions the
actual workload manifest at request time.

## Versions and what changed

The version overlays correspond to tagged releases (see
`kustomize/README.md`'s version table: `master`, `v1.0`, `v1.1`, `v1.3`,
`v2.0`, each with a `-gpu` counterpart, plus `local` for development).
`v2.0` is the current, reworked release — React 19 frontend, async
Litestar/SQLAlchemy backend and federated backend, modernized ML service
dependency stacks, and `web3` 7.x — documented in the repo root
README/`FUTURE.md`. As noted above, that rework required no changes to
`base` itself, only new `images:`/`configMapGenerator` entries in
`v2.0`/`v2.0-gpu`, since it changed what runs inside the containers, not
the shape of the Kubernetes resources wrapping them.

## Adding a new overlay version

Based on the existing pattern, a new tagged version overlay would:

1. Create `kustomize/vX.Y/kustomization.yaml` with `resources: ["../base"]`,
   a `configMapGenerator` (`behavior: merge`) supplying that version's
   four training/inference image names, and an `images:` block
   remapping `kafka-ml-backend`, `kafka-ml-frontend`,
   `kafka-ml-kafka_control_logger`, `kafka-ml-pthexecutor`, and
   `kafka-ml-tfexecutor` to the real registry name and `vX.Y` tag.
2. Create `kustomize/vX.Y-gpu/kustomization.yaml` with `resources:
   ["../vX.Y"]`, `components: ["../components/gpu-executor-images"]`,
   and its own `configMapGenerator` merge supplying the `-gpu`-suffixed
   image names.
3. Add both rows to the version table in `kustomize/README.md`.
4. Only touch `base/` if the new release actually changes a Kubernetes
   resource shape (new container, new port, new RBAC verb) — a
   dependency/stack rewrite alone, as `v2.0` showed, does not require it.

## The federated overlay tree

`federated-module/kustomize/` is a separate, parallel overlay tree with
the same structure (`base`, `local`, `master`/`master-gpu`, `v1.1`/
`v1.1-gpu`, `v2.0`/`v2.0-gpu`, its own `base/resources/role.yaml`) for
the federated satellite service's own resources
(`federated-backend-deployment.yaml`, `federated-backend-service.yaml`,
`federated-model-control-logger.yaml`,
`federated-data-control-logger.yaml`,
`federated-kafkaml-configmap.yaml`). It is deployed alongside, not
instead of, this `kustomize/` tree — see [federated-module](./federated-module)
for what that service does.

## See also

- [backend](./backend) — `app/job_manifest_generator.py` builds the
  training/inference Job manifests these RBAC resources authorize at
  runtime.
- [federated-module](./federated-module) — deployed via the sibling
  `federated-module/kustomize/` overlay tree, and whose
  `kubernetes_deploy.py` plays the same dynamic-manifest role for edge
  training Jobs.
