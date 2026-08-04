---
sidebar_position: 4
---

# Security: Threat Model for `exec()`'d Model Code

**Anyone who can reach the backend API can run arbitrary code on the
executor/training/inference pods.** This is core to how Kafka-ML works —
models are pasted as Python in the Web UI (the Configuration/Deployment
views), sent to the backend, and `exec()`'d for real:

- `mlcode_executor` (`tfexecutor`/`pthexecutor`) — every model definition
  is checked by literally `exec()`-ing it before a deployment is allowed
  to proceed.
- `model_training` (`tensorflow`/`pytorch`) and `model_inference/pytorch`
  — the same code is `exec()`'d again inside the training/inference pod
  to reconstruct the model (`model_inference/tensorflow` differs: it
  loads an already-serialized `.h5` file, no `exec()`).
- `federated-module`'s `federated_model_training/tensorflow` — same as
  `model_training/tensorflow`.

This isn't a bug to fix — dynamic model code is the product — but it
does mean **this tool must not be exposed to untrusted users without the
isolation below in place.** Kafka-ML has no user-account system at all;
anyone who can reach the backend's HTTP API has this level of access.

## Mitigations in place

- **Non-root containers.** Every image on the `exec()` surface
  (`mlcode_executor`, `model_training`, `model_inference`) creates and
  runs as a dedicated `kafkaml` user (uid 1000), not root.
- **Dropped Linux capabilities, no privilege escalation, default
  seccomp.** Every static Deployment and every dynamically-created
  training/inference Job sets `runAsNonRoot: true`,
  `allowPrivilegeEscalation: false`, `capabilities: {drop: [ALL]}` on the
  container, and `seccompProfile: {type: RuntimeDefault}` on the pod.
- **NetworkPolicies (opt-in).** Restrict the executor Deployments and
  training-job pods to only the egress they actually need (Kafka,
  backend, DNS). **Not enabled by default** — Docker Desktop's
  Kubernetes doesn't enforce NetworkPolicy at all, so this couldn't be
  validated end-to-end there; enable it in your own cluster only after
  confirming your CNI enforces NetworkPolicy.

## Not done / explicitly out of scope for now

- **Read-only root filesystem** — would need code changes first (several
  services write scratch files as plain relative paths under the same
  directory the application code lives in).
- **AppArmor profiles** — cluster/node-dependent, not attempted.
- **gVisor/Firecracker-level sandboxing** — only worth the operational
  complexity if this is ever exposed to genuinely untrusted (not just
  unauthenticated-but-trusted) users.
- **At-rest encryption for stored cluster credentials** — the inference
  deployment form's external-cluster token is stored in plain SQLite,
  with no at-rest encryption.
