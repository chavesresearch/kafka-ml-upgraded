# Kafka-ML integration tests

Real, API-driven integration tests for Kafka-ML. Each test creates a
model, a configuration, and a deployment through **the real
`backend-litestar` REST API** - the same calls a frontend would make, not
direct database seeding - which makes the backend submit **real
Kubernetes Jobs/ReplicationControllers**. Each test then sends real data
over a real Kafka broker and polls until a real training/inference result
comes back. Nothing here is mocked: if the backend can't actually deploy a
working training container, these tests fail.

## What this caught

Building this suite found a genuinely critical bug that had never been
exercised before: every one of `backend-litestar`'s three real Kubernetes
deploy code paths (`create_deployment`, `stop_inference`,
`deploy_inference`) did `await k8s_config.load_incluster_config()`, but
`kubernetes_asyncio.config.load_incluster_config` is a **sync** function
in `kubernetes-asyncio==32.0.0` - it returns `None`, not a coroutine, so
every single real deployment attempt failed with `TypeError: object
NoneType can't be used in 'await' expression`. This had never been caught
before because `backend-litestar`'s own port session explicitly noted this
code path was untested against a real cluster (see its `CLAUDE.md`) -
every prior round of `model_training`/`model_inference`/`federated-module`
testing this project did manually constructed and applied its own pod/Job
YAML instead of exercising the backend's actual `/deployments/`,
`/results/inference/{id}` endpoints. This suite is the first thing to
actually drive a real deployment through the real API, and it immediately
found this. See `backend-litestar/app/controllers/deployments.py` and
`inferences.py` for the fix (drop the `await`).

A near-identical Kubernetes-client bug (a blank `Configuration()`
discarding the in-cluster default) was separately found in
`federated-module-upgraded/federated_backend` and fixed in both places -
see that module's `CLAUDE.md`.

## Prerequisites

- Docker Desktop's Kubernetes, `kafkaml` namespace, with `backend`,
  `kafka`, `tfexecutor`, `pthexecutor` running and healthy.
- `backend`/`kafka` reachable **directly from the host** at
  `localhost:8000`/`localhost:9094` - Docker Desktop maps `LoadBalancer`
  services to `localhost` automatically, and `kafka-deployment.yaml`
  already has a `PLAINTEXT_HOST://localhost:9094` listener for exactly
  this - no `kubectl port-forward` needed. Confirm with:
  ```
  curl http://localhost:8000/results/
  ```
- `kafkaml-configmap`'s `*.training.image`/`*.inference.image` keys
  pointing at locally-built `:test` images (`kafka-ml-model-training-tensorflow:test`,
  `kafka-ml-model-training-pytorch:test`,
  `kafka-ml-model-inference-tensorflow:test`,
  `kafka-ml-model-inference-pytorch:test`), and the `backend` deployment
  restarted after patching the configmap so it picks up the new values:
  ```
  kubectl patch configmap kafkaml-configmap -n kafkaml --type merge -p '{"data":{
    "tensorflow.training.image": "kafka-ml-model-training-tensorflow:test",
    "tensorflow.inference.image": "kafka-ml-model-inference-tensorflow:test",
    "pytorch.training.image": "kafka-ml-model-training-pytorch:test",
    "pytorch.inference.image": "kafka-ml-model-inference-pytorch:test"
  }}'
  kubectl rollout restart deployment backend -n kafkaml
  ```
  (`job_manifest_generator.py` sets `imagePullPolicy: "Always"` in the
  wrong place in the manifest - pod spec level, not per-container - so
  Kubernetes silently ignores it and each container falls back to its own
  default, `IfNotPresent` for an explicitly-tagged image. This is a
  pre-existing bug, not fixed here, but it's *why* pointing at a local
  `:test` tag works without a real registry - don't rely on this if the
  bug ever gets fixed.)
- The `backend` pod's service account (`kafkaml`) needs `create`/`get`/
  `list`/`delete`/`watch` on `jobs`/`replicationcontrollers`/`pods` in the
  namespace - already the case if you're using `kustomize/base/resources/role.yaml`.

## Running

```
uv sync
uv run pytest -v -s
```

Or run any single file directly, e.g. `uv run python3 test_case1_single_classic.py`.

Each test is independent (unique names via `uuid.uuid4()`), so they can
run in any order or in isolation. Real training takes real wall-clock
time - expect the full suite to take a few minutes, not seconds.

## What's covered, and what isn't

| Test | What it exercises |
|---|---|
| `test_case1_single_classic.py` | TF CASE=1: single, non-distributed, non-incremental |
| `test_case2_single_incremental.py` | TF CASE=2: single, incremental (`OnlineRawSink`, streaming Kafka consumer) |
| `test_case3_distributed_classic.py` | TF CASE=3: distributed (father/child model pair via the real `father` field + configuration auto-expansion) |
| `test_case4_distributed_incremental.py` | TF CASE=4: distributed + incremental together |
| `test_pytorch_classic.py` | PyTorch's one training mode (no `CASE` dispatch) |
| `test_inference.py` | Real-time TF inference: trains a model, deploys it via `POST /results/inference/{id}` (real `ReplicationController`), sends one message, checks a real prediction |

**Not covered here** (see each module's own `CLAUDE.md` for why, and what
verification *was* done instead):

- **Federated modes (CASE 5-9)** - CASE=5 was verified with a real,
  complete, multi-service end-to-end round (main trainer,
  `federated_backend`, both control-logger relays, and a real edge worker
  Job) - see `federated-module-upgraded/CLAUDE.md` and
  `model_training-upgraded/tensorflow/CLAUDE.md`'s CASE=5 section for the
  full record. It isn't automated into *this* suite because it needs
  `federated_backend` and both logger services also running, which this
  suite's prerequisites don't currently stand up. Worth adding here later.
- **Blockchain (CASE=9)** - needs a real or local-testnet Ethereum node,
  import/compile-level verification only.
- **Semi-supervised/unsupervised training** - not attempted in any part
  of this project's verification so far.
- **PyTorch inference** - `model_inference-upgraded/pytorch` was verified
  manually (see its `CLAUDE.md`); not yet added to this API-driven suite.
- **Confusion matrix generation**, **AVRO input format** - see the
  relevant `CLAUDE.md` files; both are either untested or (AVRO) known
  pre-existing dead code, unrelated to this suite.

## Gotchas worth keeping if you extend this

- **Distributed models**: `mlcode_executor`'s `format_ml_code` expects the
  submitted code to end in a *bare* expression (`tf.keras.Model(...)`),
  not a `model = ...` assignment, and the code string must not end with a
  trailing newline - see `common.py`'s `TF_CLOUD_MODEL_CODE`/
  `TF_EDGE_MODEL_CODE` for a template, and
  `model_training-upgraded/tensorflow/CLAUDE.md` for why.
- **Creating a distributed configuration**: only pass the *root* (father-less)
  model's id to `POST /configurations/` - `_expand_with_children` walks the
  father/child chain automatically. Passing the child's id too doesn't
  hurt, but isn't necessary.
- **Streaming/incremental modes need a real wait before sending data**:
  the training container's streaming Kafka consumer group has no
  committed offset, so it starts from `latest` - data produced before it
  actually joins the group is silently invisible to it forever. `sleep`
  long enough after `create_deployment` before sending the first burst
  (observed: ~15s is enough for a single non-distributed model, ~35s
  needed for distributed+incremental - two model downloads plus building
  the combined multi-output graph takes measurably longer). If you see a
  training pod's log show `Resetting offset for partition ... to offset N`
  where `N` equals the total number of messages you already sent, that's
  this race, not a real bug - increase the wait.
- **PyTorch kwargs use a different string format than TensorFlow's** -
  `tf_kwargs_fit`/`tf_kwargs_val` and `pth_kwargs_fit`/`pth_kwargs_val` are
  both `"key=value, key2=value2"` strings (parsed by
  `parse_kwargs_fit`'s `eval()` per value - matches the platform's
  existing trust model, not hardened, see `backend-litestar/CLAUDE.md`),
  but the *keys* differ: TensorFlow's `.fit()` kwargs (`epochs=1`) vs.
  PyTorch/ignite's trainer-run kwargs (`max_epochs=1`).
- **Real inference deployments are long-running** (a
  `ReplicationController`, not a `Job` with a TTL) - always clean up with
  `POST /inferences/{id}` (stop) then `DELETE /inferences/{id}` in a
  `finally` block, or you'll leak a running pod per test run.
