# Future upgrades

A working list of upgrades for this fork, ordered by severity within each
section. Originally written from a pass over the whole tree as of
2026-07-31, right after the Angular→Vue frontend rewrite; revisited on
2026-08-04 after the Django→Litestar backend, Flask→Litestar
`mlcode_executor`, and dependency-modernized `model_training`/
`model_inference`/`federated-module`/`datasources` ports were all cut over
into their original directory names (`backend/`, `frontend/`, etc. - the
old implementations now live only in the separate `../kafka-ml` reference
checkout, not in this repo); revisited again later the same day after a
second frontend rewrite (React 19 + shadcn/ui, replacing Vue) was cut over
the same way — except this time the Vue implementation it replaced was
deleted outright rather than preserved anywhere, since Vue was itself a
rework artifact from this same project, not part of the original
pre-rework codebase `../kafka-ml` preserves. Items resolved by these
cutovers are kept (struck through, with a **done** note) rather than
removed, so the history of what used to be true here isn't lost.
Re-evaluate before acting — some items may already be stale by the time
you read this.

Split into three top-level sections, **TODO**, **Not planned (short
term)**, and **Completed** (the TODO/Completed split added 2026-08-07 -
before this, open and resolved items were interleaved within each
severity level, which made it hard to see the real remaining backlog at
a glance; "Not planned" carved out the same day, for real findings that
just aren't worth doing yet - see that section's own intro for why that's
different from simply not tracking them). Each is itself ordered by
severity (Critical → High → Medium → Low, then the frontend-specific
follow-ups), and items are renumbered sequentially within each severity
subsection of each top-level section - a numbered cross-reference like
"High item 9" always means item 9 of whichever of the three subsections
(TODO/Not planned/Completed) it's actually pointing at, called out
explicitly wherever that isn't the same section the reference itself
lives in.

Severity guide: **Critical** = security/availability risk or actively
breaks correctness guarantees today. **High** = real cost or risk, no active
incident. **Medium** = maintainability/debt, no immediate risk. **Low** =
nice-to-have polish.

## TODO

### Medium

1. **No CI job runs `integration-tests/` automatically.** A
   `workflow_dispatch`-triggered job (`.github/workflows/
   integration-tests.yml`) is prepared and ready to dispatch on a
   `[self-hosted, kafka-ml-local-cluster]` runner - it can't run on a
   GitHub-hosted runner at all, since `integration-tests/README.md`'s own
   Prerequisites need a real local Kubernetes cluster with `backend`/
   `kafka`/`tfexecutor`/`pthexecutor` already deployed and reachable at
   `localhost:8000`/`localhost:9094`. **Blocked on registering an actual
   self-hosted runner with that label** (Settings -> Actions -> Runners ->
   New self-hosted runner on a machine that already satisfies those
   prerequisites) - the workflow itself has a fail-fast reachability
   check (`curl localhost:8000/results/`) and accepts an optional
   `test_pattern` input (pytest `-k` expression) or a
   `run_real_mnist_case` input (one `mnist_case*.py` script) so a partial
   run doesn't require dispatching the whole multi-minute suite. Prepared
   2026-08-07; not yet actually dispatched/verified against a real
   runner - say so explicitly if asked whether this has run in CI, not
   just whether the workflow file exists.

2. **All 7 frontend list views show a misleading "No results." empty
   state during the initial fetch** - `ModelList`, `ConfigurationList`,
   `ResultList`, `DatasourceList`, `IoTDeviceList`, `DeploymentList`, and
   `InferenceList` all render the empty-state message whenever their
   array is empty, with no separate loading flag tracked while the
   initial `get*()` call is still in flight - so a user on a slow
   connection briefly sees "no data exists" before it flips to the real
   rows. Found in a 2026-08-07 audit.

### `frontend`-specific follow-ups

1. **Feature-parity audit vs. the previous frontend hasn't been done by a
   human yet.** Applies transitively through both rewrites: the Angular→Vue
   audit was never done (noted here since 2026-07-31), and neither has a
   Vue→React one. Each rewrite was verified against the live backend
   (CRUD + WebSocket smoke tests, Playwright passes of the UI) but not
   clicked through screen-by-screen by a person. Not a gate on anything -
   both older implementations are already fully retired (Angular preserved
   at `../kafka-ml/frontend`; Vue not preserved anywhere, see this file's
   intro) - just still worth doing.

## Not planned (short term)

Real, verified findings that aren't going to be worked on soon - not
because they're wrong, but because fixing them properly needs either a
design decision (not just a patch) or infrastructure this project
doesn't have reason to invest in yet. Re-evaluate rather than dismiss if
one of these comes up again - "not planned" is a scoping call made on
2026-08-07, not a permanent judgment that the finding is unimportant.

### High

1. **`federated_backend` has the same SQLite-on-ephemeral-filesystem
   design as `backend`, undocumented for this service specifically.**
   `federated-module/federated_backend/app/config.py` defaults to
   `sqlite+aiosqlite:///.../db.sqlite3`; neither
   `kustomize/base/resources/backend-deployment.yaml` nor
   `federated-backend-deployment.yaml` mounts any volume, so every
   `kubectl rollout restart deployment/federated-backend` silently wipes
   every registered `ModelSource`/`Datasource` row (any federated
   registration mid-flight at restart time is lost, not just delayed).
   Found in a 2026-08-07 audit. **Why not now**: mounting a PVC ourselves
   in the base kustomize manifests would mean assuming a `StorageClass`
   exists on whatever cluster this gets deployed to (e.g. a
   `local-path-provisioner`-style dynamic provisioner) - true for this
   project's own Docker Desktop dev setup, but not something the base
   manifests should assume on someone else's cluster. Deliberately **not
   mounting anything** rather than guessing - if you need
   `federated_backend` to survive restarts, add your own `PersistentVolume`/
   `PersistentVolumeClaim` to the deployment, sized and classed for your
   own cluster's storage, and point `DATABASE_URL` at a path under that
   mount. Worth documenting this explicitly next to `backend`'s identical
   restart-wipes-state behavior (same underlying design, same reasoning
   for not solving it at the base-manifest level).

2. **PyTorch training only supports CASE=1 (single, non-distributed,
   non-incremental, non-federated classic training) - `model_training/
   pytorch/training.py` has no `CASE` env var dispatch at all, while
   TensorFlow implements all 9 CASEs.** Nothing in the backend or
   frontend gated this until 2026-08-07 (see Completed/High item 18
   below for the fix that closed the specific silently-wrong federated
   case) - a PyTorch deployment configured as distributed/incremental
   still isn't implemented, just no longer silently mishandled for the
   federated case specifically. A full phased implementation plan -
   dispatch skeleton, then CASE 2 (incremental, moderate cost, has a
   proven TF blueprint to port from), CASE 3/4 (distributed, expensive,
   no PyTorch precedent for the submodel-chaining design), CASE 5-8
   (federated, expensive, additionally blocked on a completely
   nonexistent `federated-module/federated_model_training/pytorch/`
   edge-worker service - confirmed only a `.gitkeep`), CASE 9
   (blockchain, expensive but cheaper once CASE 5 exists) - is written up
   in `model_training/pytorch/CASE_2_9_PLAN.md`, including a suggested
   one-day scope (Phase 0 + CASE 2) and per-phase verification bars.
   Found/scoped in a 2026-08-07 audit. **Why not now**: this is a real
   feature-development effort (the plan's own cost assessment puts
   several phases at "expensive, no in-repo precedent"), not a bug fix or
   hardening pass - scoped as its own future work, not squeezed into a
   backlog-clearing session. Pick up via the linked plan whenever PyTorch
   parity becomes the priority.

### Medium

1. **No resource `requests`/`limits` or liveness/readiness probes on any
   of the 6 base Deployments** (`backend`, `frontend`, `tf-executor`,
   `pth-executor`, `kafka-control-logger`, `federated-backend` - grepped
   every manifest under `kustomize/base/resources/`, zero hits on either
   field), **and none on dynamically-generated training/inference Jobs
   either** (`backend/app/job_manifest_generator.py`,
   `federated_backend/app/kubernetes_deploy.py` - grepped, nothing).
   Distinct from the GPU-specific resource-limit code path this project
   already has for `-gpu` variants. Without requests/limits, a runaway
   training container (TensorFlow/PyTorch have no built-in memory cap)
   can starve or OOM-kill neighboring pods on the same node instead of
   being contained to its own; without probes, Kubernetes has no signal
   to restart a hung-but-still-running pod. Found in a 2026-08-07 audit.
   **Why not now**: real values need real load-testing per service (a
   too-tight memory limit on a training Job would OOM-kill legitimate
   training runs, not just runaway ones) - this is a tuning exercise, not
   a mechanical fix, and this project's own local-dev/single-node
   verification loop doesn't exercise multi-tenant resource pressure at
   all. Worth doing before any real multi-tenant or production
   deployment, not before then.

2. **Kafka has no transport security anywhere in the stack.** Grepped
   every `KafkaProducer`/`KafkaConsumer`/`AIOKafkaConsumer` construction
   repo-wide (`datasources`, `model_training/*`, `model_inference/*`,
   `mlcode_executor/tfexecutor`, `kafka_control_logger`,
   `federated-module/*`, `backend/app/websocket.py`) - zero SASL/SSL
   config anywhere; every client connects to `BOOTSTRAP_SERVERS` in
   plaintext with no authentication. Found in a 2026-08-07 audit; now
   documented in `website/docs/security.md`'s "Not done" section (see
   Completed/Medium item 21 in the Completed section below) so it's at
   least disclosed, even unfixed. **Why not now**: this is a
   deployment-topology assumption
   (fine inside a trusted cluster network, the only topology this
   project currently documents/tests against), not a single code
   change - every one of the ~10 services listed above would need its
   own SASL/SSL config plumbed through from Kafka broker setup down to
   each client construction, and there's no broker-with-auth in this
   project's own local dev/CI loop to verify against. Worth doing before
   deploying across any less-trusted network boundary, not before then.

3. **No PodDisruptionBudget anywhere in the repo.** Muted impact today
   since every base Deployment is already `replicas: 1` (a PDB can't
   protect a true singleton from eviction, only guarantee *how many* of
   several replicas stay up). Found in a 2026-08-07 audit. **Why not
   now**: genuinely low value until something in this repo actually runs
   at more than 1 replica - adding PDBs today would be unverifiable
   (nothing to test the "protects N-1 replicas" behavior against) and
   pure boilerplate. Revisit the moment any service's `replicas` moves
   past 1.

## Completed

### Critical

1. ~~Backend runs on end-of-life dependencies (Django 3.2.13, DRF 3.11.0,
   channels/daphne 3.x).~~ — **done** (2026-08-04): `backend/` is now a
   from-scratch Litestar/SQLAlchemy async port (see `backend/CLAUDE.md`) -
   no Django, DRF, or channels dependency remains at all. The old Django
   implementation is preserved for reference at `../kafka-ml/backend` if
   this history is ever needed.

2. ~~`DEBUG` and `ALLOWED_HOSTS` still default to insecure values.~~ —
   **done** (2026-08-04, commit `de307eb`): this entry itself lagged the
   actual fix by a doc-update gap, caught while triaging the backlog
   again on 2026-08-05. `app/config.py`'s `_validate_production_safety`
   refuses to boot when `ENVIRONMENT=production` and either `DEBUG` is
   still `True` or `ALLOWED_HOSTS` is still `["*"]` - covered by
   `backend/tests/test_config.py` (5 cases). `kustomize/base` now sets
   `debug=0`/`environment=production` explicitly in its ConfigMap rather
   than relying on the fail-open default, so a bare `kubectl apply` of
   these manifests is already covered; a hand-trimmed Deployment that
   dropped `ENVIRONMENT` entirely would still boot insecure (fails open
   only if that one var is also missing) - a real but much narrower gap
   than the original framing, not worth closing further for an
   operator-error case this niche.

3. ~~User-submitted model code is `exec()`'d with no sandboxing.~~ —
   **partially done** (2026-08-04). This is core to how Kafka-ML works
   (see the new "Threat model: exec()'d model code" section in the root
   README - not a "bug" to eliminate, an inherent trust boundary to
   document and reduce the blast radius of). Done: non-root containers
   (verified with real `docker build`+`docker run` on both base-image
   families), dropped capabilities/no-privilege-escalation/default
   seccomp on every static Deployment and dynamically-created Job
   (`backend/app/job_manifest_generator.py`, `federated_backend`'s
   `deploy_on_kubernetes`), opt-in NetworkPolicies (`kustomize/base/
   resources/networkpolicies.yaml` - not enabled by default since Docker
   Desktop's Kubernetes doesn't enforce NetworkPolicy at all, confirmed
   empirically rather than assumed), and the README threat-model note
   itself. **Not done, and why**: read-only root filesystem (would need
   real code changes first - these services write scratch files as plain
   relative paths under the same directory the code lives in), AppArmor
   (cluster/node-dependent, can't verify locally), gVisor/Firecracker
   (only worth it if ever exposed to genuinely untrusted users). Full
   detail in the README section - read that instead of re-deriving.

4. ~~No CI job runs any of the existing test suites.~~ — **done**
   (2026-08-04). Every Python service now has a real `tests/` suite and a
   `test` job (`uv run pytest`) that its `build-*` job `needs:`, gated off
   on `pull_request` events - same test-then-build shape `frontend.yml`
   already used. 134 tests total: `backend` (21, was already 16 - added
   `test_config.py` for the new fail-closed-in-production check),
   `mlcode_executor/{tfexecutor,pthexecutor}` (8+7, real Litestar
   `TestClient` endpoint tests - found and fixed a real Keras 3
   `compile=False` bug in `tfexecutor`'s `/convert_to_tflite/` along the
   way), `model_training/{tensorflow,pytorch}` (29+4),
   `model_inference/{tensorflow,pytorch}` (14+9), and
   `federated-module/{federated_backend,federated_model_training/
   tensorflow}` (13+29). All are unit/endpoint-level tests against pure
   decode/dispatch/matching logic - the 9-CASE training-mode dispatch
   itself is still only verified via the real end-to-end cluster runs
   documented in each service's own CLAUDE.md, impractical to reproduce in
   CI. `federated_data_control_logger`/`federated_model_control_logger`
   were deliberately skipped - both are ~100-line scripts with everything
   inline under `if __name__ == '__main__':`, nothing factored out to
   unit-test without restructuring working code beyond what "add tests"
   justifies. Also found and fixed, while wiring this up: two CI-breaking
   `context:` bugs (`tensorflow_model_training.yml`,
   `federated_tensorflow_model_training.yml` built from their own
   subdirectory, but both Dockerfiles COPY the sibling `tf-kafka-dataset`
   package and need the repo root as context - reproduced the failure
   with a real `docker build` before fixing, then confirmed the fix
   builds clean) - these workflows had apparently never actually been
   triggered, or this would have failed every time.
   **Correction, 2026-08-06**: that last sentence was more right than
   realized at the time - these workflows really had never actually
   succeeded on GitHub Actions itself (this "done" write-up was based on
   `uv run pytest`/`docker build` working locally, never on watching a
   real triggered run go green). `gh run list` showed a **100%
   `startup_failure` rate across every workflow in this repo except
   `website.yml`**, the entire time - the repo's default `GITHUB_TOKEN`
   permissions are read-only, and every workflow calling the reusable
   `build.yml` (which needs `packages: write` to push images) never
   declared its own `permissions:` block, so the call was rejected before
   any job even started. Fixed by adding an explicit `permissions:
   {contents: read, packages: write}` to all 13 affected workflows, plus
   `workflow_dispatch` triggers so they can be re-run on demand for
   verification. Confirmed via real `gh workflow run` + `gh run watch`
   calls, not assumed: `test` jobs now pass end-to-end (found and fixed
   two more real bugs *this* surfaced - `astral-sh/setup-uv@v9` doesn't
   resolve as a floating tag past v8's move to immutable releases, pinned
   to the exact `v9.0.0` instead; and `frontend/src/lib/utils.ts` -
   imported by nearly every shadcn/ui component - had never actually been
   committed to git at all, silently masked by an overly broad unanchored
   `lib/` entry in the root `.gitignore`, gitignore.io Python-packaging
   boilerplate that was never meant to reach into `frontend/src/`). The
   `build-*` jobs now correctly progress all the way to `docker/login-action`
   and stop there with "Password required" - this fork has no
   `DOCKERHUB_KEY` secret configured, correctly so, since it isn't meant
   to publish to `ertis`'s Docker Hub namespace itself.

5. ~~Blockchain wallet private key shipped in plaintext to pods that
   `exec()` untrusted model code.~~ — **done** (2026-08-06). Found by a
   4-agent fresh-eyes rescan (see Medium items 8-14 below for the rest of
   that pass). `job_manifest_generator.py`/`federated_backend/app/
   kubernetes_deploy.py` both re-injected `FEDML_BLOCKCHAIN_WALLET_KEY` as
   a literal `value:` env var into every CASE=9 training Job - a straight
   line from "submit a blockchain-enabled model" (the platform's own
   documented exec() threat model) to stealing the key that pays on-chain
   rewards. Fixed at the root: the key is no longer in the
   `kafkaml-configmap`/`federated-kafkaml-configmap` ConfigMaps at all
   (plaintext, readable to anyone with basic `get` access); backend's own
   copy now comes from a `secretKeyRef` against a new
   `kafkaml-blockchain-credentials` Secret (`optional: true`, same
   pattern as the existing `KUBE_TOKEN`/`KUBE_HOST`), and the training
   Job/federated worker manifests now point their own `ETH_WALLET_KEY` at
   that *same* Secret via `secretKeyRef` too, instead of copying the
   resolved value out of the backend process's own memory. Local dev
   overlay creates the Secret from a literal `kustomize/local/resources/
   blockchain-wallet-secret.yaml` (Anvil's well-known dev key, not a real
   secret - see that file's own comment). Verified live: rebuilt and
   redeployed `backend`/`federated-backend`, confirmed both pods resolve
   the real key correctly (`kubectl exec ... printenv`), confirmed the
   literal key value appears nowhere in any Deployment/Job spec except the
   Secret's own `stringData`, and ran a real CASE=1 deployment end-to-end
   afterward to confirm nothing broke.

6. ~~A spoofable `Origin` header becomes a URL real IoT hardware fetches
   and auto-executes.~~ — **done** (2026-08-06), same rescan.
   `backend/app/controllers/iot_devices.py`'s `deploy_to_iot_devices`
   used `request.headers.get("Origin", settings.FRONTEND_URL)` to build
   the URL embedded in a Tasmota Berry script pushed to a real device over
   MQTT - a forged `Origin` on `POST /results/inference-iot/{id}`
   redirects a real device into downloading and running attacker-supplied
   firmware. Fixed by using `settings.FRONTEND_URL` unconditionally - the
   `request: Request` parameter (and its now-unused import) were removed
   entirely, not just the one line, since nothing else in the handler
   used it. `uv run pytest -v` (30/30, then 33/33 after the Medium-items
   test additions below) still passes.

7. ~~`backend/app/controllers/iot_devices.py`'s `deploy_to_iot_devices`
   passed a hardcoded `timeout=30` on the one `httpx` call to
   `convert_to_tflite/` that can legitimately take *longer* than 30s -
   `tfexecutor`'s int8-quantization path polls a live Kafka topic with
   `consumer_timeout_ms=60000` before conversion even starts.~~ —
   **done** (2026-08-07). Found during a fresh audit right after the
   shared `httpx.AsyncClient` timeout was bumped 5s -> 180s (High item 12
   below/`mlcode_executor`'s queue-deadlock fix) specifically to cover
   this class of call - this one call site was explicitly overriding it
   back down, guaranteeing a timeout on any real int8-quantized IoT
   deployment against a moderately slow topic. Removed the override;
   the call now inherits the shared client's 180s default.

### High

1. ~~Two frontends now coexist (`frontend/` Angular + `frontend-vue/`
   Vue).~~ — **done** (2026-08-04): cut over. `frontend/` became the Vue
   app; the old Angular implementation is preserved for reference at
   `../kafka-ml/frontend`. Superseded the same day by a second cutover
   (see next item) — `frontend/` is React now, not Vue.

2. ~~Two frontends now coexist (`frontend/` Vue + `frontend-react/`
   React).~~ — **done** (2026-08-04): cut over. `frontend/` is now the
   React 19 + shadcn/ui rewrite; the Vue implementation it replaced was
   deleted outright, not preserved anywhere (unlike the Angular cutover
   above, Vue isn't part of the original pre-rework codebase `../kafka-ml`
   exists to preserve — it's in git history before this cutover's commit
   if it's ever needed). `kustomize/base/resources/frontend-deployment.yaml`
   needed zero changes - same image name (`kafka-ml-frontend`) the Vue and
   Angular builds both used. See `frontend/CLAUDE.md`.

3. ~~Cluster credentials are handled as plaintext freeform input.~~ —
   **partially done** (2026-08-04). The RBAC scope-down turned out to
   already be a non-issue: `kustomize/base/resources/role.yaml` (and
   `federated-module/kustomize/base/resources/role.yaml`) were already a
   namespaced `Role` with a specific resource/verb list (`deployments`,
   `jobs`, `pods`, `replicasets`, `services`, `replicationcontrollers`;
   `create`/`get`/`list`/`delete`/`watch`) — not `cluster-admin`, and no
   `ClusterRole`/`ClusterRoleBinding` anywhere in the repo grants more
   (verified by grep). This item's "cluster-admin" framing was stale.
   What *was* real and is now fixed: `backend/app/schemas/
   __init__.py`'s `inference_dict` echoed the plaintext external-cluster
   `token` back on every `GET /results/inference/{id}` — removed (it's
   write-only: no PUT/PATCH endpoint exists for inferences, and
   `frontend`'s `Inference` type never declared or read the field).
   `kustomize/base/resources/backend-deployment.yaml` also documented the
   optional default `KUBE_TOKEN`/`KUBE_HOST` fallback as a raw commented
   `value: ...` — replaced with an `optional: true` `secretKeyRef` against
   a `kafkaml-kube-credentials` Secret an operator creates out-of-band, so
   there's no plaintext-in-git pattern being modeled anymore. **Not done:**
   the per-inference `token`/`external_host` submitted through the web
   form is still stored as a plain SQLite column
   (`app/models.py:209`) — there's no at-rest encryption for
   it, unlike the RBAC/API-response issues above this is inherent to the
   feature (arbitrary external-cluster credentials the platform doesn't
   otherwise manage) and would need real app-level encryption to close,
   not just a Secret reference.

4. ~~Python 3.8 base images across the board (`backend/Dockerfile`,
   `kafka_control_logger/Dockerfile`,
   `federated-module/federated_backend/Dockerfile` all pinned
   `FROM python:3.8.6`, EOL October 2024).~~ — **done** (2026-08-04): all
   three now build from `python:3.12-slim` as part of their respective
   ports/uv migrations. `model_training`/`model_inference`/`mlcode_executor`
   build from `tensorflow/tensorflow:${TFTAG}` or a configurable
   `${BASEIMG}` instead - audit those tags separately if they come up
   (see each service's own `CLAUDE.md` for the specific versions/reasoning
   already checked).

5. ~~Kustomize version sprawl.~~ — **investigated and partially
   consolidated (2026-08-04).** The premise turned out to be partly
   wrong: read all 10 `kustomization.yaml` files side by side (not just
   the directory listing) before concluding. 8 of the 10
   (`v1.0`/`v1.0-gpu`/`v1.1`/`v1.1-gpu`/`v1.3`/`v1.3-gpu`/`master`/
   `master-gpu`) were already pure Kustomize composition with **zero**
   raw resource YAML duplication - each is a ~12-line `kustomization.yaml`
   (`resources: [../base]` or `[../<version>]` + a `configMapGenerator`
   merge + an `images:` transformer), not a copy of `base`'s actual
   manifests. There's also no "GPU scheduling plugin" in any of these
   files at all (no `gpushare`/`nvidia.com/gpu` reference anywhere in
   `kustomize/`) - the `-gpu` variants only ever swapped Docker image
   tags; GPU device-plugin/scheduler setup is entirely operator-side (see
   root README's "GPU configuration" section, itself flagged stale
   separately as Medium #3). So there was no actual gpushare→NVIDIA
   migration for `v1.0`/`v1.1` to have missed.
   What *was* real: the `images:` transformer block inside each
   `{version}-gpu/kustomization.yaml` was byte-identical across all 4
   (confirmed with `diff`) - extracted into a new shared Kustomize
   Component, `kustomize/components/gpu-executor-images/`, that every
   `-gpu` overlay now references via `components:` instead of
   copy-pasting. Verified byte-identical rendered output
   (`kubectl kustomize <dir>`) before and after the refactor, for all 4
   overlays. The per-version `configMapGenerator` block still has to stay
   version-specific (it's an opaque string literal inside a ConfigMap,
   invisible to Kustomize's `images:` transformer, so the version tag
   can't be factored out the same way) - that's an inherent Kustomize
   limitation (no string templating/concatenation), not something left
   undone. Also fixed real, unrelated documentation drift found along the
   way: `kustomize/README.md`'s version table listed a `v1.1-gpu-nvidia`
   directory that doesn't exist, and was missing `v1.3`/`v1.3-gpu`, which
   do.
   **Follow-up, 2026-08-05**: two more real gaps found and fixed while
   preparing this rework for its eventual upstream release as `v2.0`.
   (1) Every versioned overlay except `base`/`federated-module/kustomize/base`
   was missing an explicit `apiVersion`/`kind` on its own
   `kustomization.yaml` (kustomize silently defaults these when absent,
   confirmed via a real `kubectl kustomize`/`kustomize build` output diff
   before/after adding them to all 20 overlays across both modules -
   byte-identical, purely additive). (2) `federated-module/kustomize/`
   already had real `master`/`master-gpu`/`v1.1`/`v1.1-gpu` overlays
   (missed on first read this session - only `base`/`local` were checked
   before concluding they didn't exist) - added `v2.0`/`v2.0-gpu` there to
   match, plus the equivalent `kustomize/v2.0`/`v2.0-gpu` for the main
   module. Both new overlay pairs target `ertis/kafka-ml-*`/
   `ertis/federated-kafka-ml-*:v2.0` (the same Docker Hub namespace every
   other version uses, per `.github/workflows/build.yml`'s
   `USERNAME: ertis`) rather than this fork's own registry, since the
   user's plan is to merge this rework upstream and cut the real `v2.0`
   release there. Verified: `kustomize build` clean on all 20 overlays,
   plus a real `kubectl apply --dry-run=server` against the live cluster
   for both `local` overlays (unchanged, matching what's actually
   deployed) and both new `v2.0` overlays (schema-valid, `configured` -
   would swap in the not-yet-published `:v2.0` images if applied for
   real). See `kustomize/README.md` and
   `federated-module/kustomize/README.md` for the current version
   tables.

6. ~~No dependency update automation.~~ — **done** (2026-08-04):
   `.github/dependabot.yml` now covers every ecosystem in the repo — 16
   `uv` entries (one per `pyproject.toml`/`uv.lock` pair), 1 `npm` entry
   (`frontend`), 13 `docker` entries (one per Dockerfile), and
   `github-actions`, all weekly. `frontend` uses pnpm but that's still the
   `npm` ecosystem value — Dependabot auto-detects the lockfile type per
   directory. (Counts as of the React cutover - was 2 npm/14 docker
   entries before `frontend-react`'s entries merged into `frontend`'s.)

7. ~~CASE=2 (`SingleIncrementalTraining`) can crash and get stuck
   "deployed" forever if zero streaming data batches arrive before its
   stream timeout.~~ — **done** (2026-08-05). Found 2026-08-04 while
   re-running `integration-tests/` as a final check after that session's
   security/CI hardening pass - reproduced 3/3 times.
   `model_training/tensorflow/mainTraining.py`'s `train_incremental_model`
   only assigned `model_trained = self.model.fit(...)` inside `if
   len(mini_ds) > 0:` - if the streaming Kafka consumer's
   `get_streaming_kafka_batches` generator timed out having yielded zero
   non-empty batches, the function fell through to `training_results =
   {'model_trained': model_trained}` with `model_trained` never assigned,
   raising `UnboundLocalError`. The trainer's outer exception handler
   caught this and looped back to polling `KAFKA_ML_CONTROL_TOPIC`
   indefinitely instead of exiting - the `TrainingResult` stayed
   `"deployed"` forever, and the pod/Job never completed. Same failure
   family as item 8 below (`federated_mainTraining.py`'s CASE=6/8
   deadlock) - this non-federated version had no retry loop at all, so it
   crashed instead of looping forever, but the underlying gap was
   identical: no recovery path when a streaming window legitimately sees
   zero messages. **Fixed** the same way as item 8: `train_incremental_model`
   now wraps the per-window loop in a retry `while`, tracking whether any
   data was received, and re-fetches a fresh generator
   (`self.get_data(self.kafka_topic, decoder)`) on an empty pass instead
   of falling through to the crash.
   Root cause of the empty-batches condition itself: a real race between
   `OnlineRawSink`'s first `.send()` call (which fires the online control
   message *and* the first data message essentially back to back) and
   the trainer's Kafka consumer-group join - `integration-tests/
   test_case2_single_incremental.py`'s fixed `time.sleep(15)` before
   creating the sink didn't actually protect against this, since the
   trainer can't start joining the *data* topic's consumer group until
   *after* it receives the control message, which only fires once the
   test starts sending. **Also fixed**: the test itself now pre-configures
   the sink's format and calls the public `send_online_control_msg()`
   explicitly before sending any real data (the gotcha
   `model_training/tensorflow/CLAUDE.md`'s CASE=2 section already
   documented but the committed test never applied), instead of relying
   on a guessed "long enough" sleep. Verified two ways: an adversarial
   repro (burst sent immediately, guaranteed to race ahead of the
   consumer join, followed by a second burst after the first generator
   fully exhausted - passed, proving the retry recovers where the old
   code would have already crashed) and the fixed committed test passing
   3/3 consecutive real runs against the live cluster (it failed with the
   pre-existing timing bug on the first real re-run this session,
   confirming the test fix was itself necessary, not just theoretical).
   `test_case1`/`test_case3`/`test_inference`/`test_pytorch_classic` (the
   non-streaming tests) all still pass, confirming no regression.

8. ~~`federated_mainTraining.py`'s `train_incremental_model` (CASE=6/8,
   federated-incremental) could deadlock permanently~~ — **done**
   (2026-08-05): the sibling bug to item 7 above, in the federated
   trainer's copy of this same "zero non-empty streaming batches" edge
   case - but a different failure mode. Where item 7's plain (non-
   federated) version crashes with `UnboundLocalError` (caught, retried
   forever, same net effect), this federated version's own retry-on-empty
   `while` loop re-iterated an already-*exhausted* Python generator
   forever - a true silent deadlock, no error, no timeout, ever. Found via
   a real end-to-end CASE=6 run with real MNIST data and real network-
   round-trip timing (the tiny-synthetic-data tests never had a large
   enough round-trip window to expose it). Fixed by re-fetching a fresh
   generator/consumer on an empty pass instead of reusing the dead one -
   see `federated-module/CLAUDE.md`'s "Real-MNIST multi-epoch pass"
   section. Item 7's plain-`mainTraining.py` sibling was fixed the
   following day (2026-08-05, see item 7 above) - both files now share
   the same fix for this root design flaw.

9. ~~`federated_backend` never marks a matched `Datasource`/`ModelSource`
   row consumed, and restarting either control-logger service replayed
   their entire retained Kafka history, re-matching every past
   registration at once.~~ — **done** (2026-08-05), fixed as part of the
   Django→Litestar rewrite (Medium item 6 below): the new
   `federated_backend` deletes both matched rows right after a successful
   deploy, and `federated_model_control_logger.py`'s
   `auto_offset_reset='earliest'` (the actual, precisely-identified cause
   of the replay - not generic "Kafka replay behavior", confirmed via
   `kubectl logs`) was dropped to match its sibling's correct `'latest'`
   default. Verified via real CASE 5/6/7/9 re-runs across two separate
   service restarts: zero duplicate Jobs both times. See
   `federated-module/CLAUDE.md`'s rewrite section for the full record.

10. ~~Inference pods run as root with every capability - training Jobs are
    hardened, inference isn't.~~ — **done** (2026-08-06), same fresh-eyes
    rescan as Critical items 5-6 above. `backend/app/controllers/
    inferences.py`'s `_single_inference_manifest`/
    `_distributed_inference_manifest` set no `securityContext` at all -
    since `model_inference/pytorch` also `exec()`s submitted model code,
    a PyTorch inference deployment ran untrusted code as root with full
    capabilities, contradicting the README's own claim that this
    hardening covers "every dynamically-created training/inference Job."
    Fixed by importing and reusing `job_manifest_generator.py`'s existing
    `_HARDENED_POD_SECURITY_CONTEXT`/`_HARDENED_CONTAINER_SECURITY_CONTEXT`
    constants in both manifest functions - confirmed both inference
    images already run a `useradd --uid 1000`/`USER kafkaml` non-root
    setup before assuming `runAsUser: 1000` was safe. `uv run pytest`
    still 30/30 (33/33 after the additions below).

11. ~~Most static Deployments have no `securityContext`, and backend's own
    Dockerfile runs as root.~~ — **done** (2026-08-06), same rescan. Only
    `tf-executor`/`pth-executor` had the hardening block; `backend`,
    `frontend`, `kafka-control-logger`, and all 3 federated-module
    services (`federated-backend`, `federated-data-control-logger`,
    `federated-model-control-logger`) had none, and `backend/Dockerfile`
    had no `USER` directive at all - unlike its own sibling
    `federated_backend/Dockerfile`, which already added a non-root user
    for the identical kind of service. Fixed: the same `useradd
    --create-home --uid 1000 kafkaml && chown -R kafkaml:kafkaml
    /usr/src/app` + `USER kafkaml` pattern added to all 5 Dockerfiles
    that were missing it (`frontend`'s Alpine-based nginx image needed
    `adduser`, not `useradd` - Alpine's busybox has no shadow-utils - plus
    `chown`-ing `/etc/nginx/conf.d`/`/var/cache/nginx`/`/run`, since
    `start.sh` templates a config file and nginx itself needs to create
    its own runtime dirs; kept on port 80 via `NET_BIND_SERVICE` rather
    than moving to an unprivileged port, since nothing else needed to
    change). Same `securityContext` block added to the 5 corresponding
    Deployment manifests. Verified live: rebuilt all 5 images, redeployed,
    confirmed every pod `Running`/`Ready` with `kubectl exec ... id`
    showing `uid=1000` in each, confirmed `curl` through the frontend's
    nginx (still binding port 80 correctly as non-root) and the backend
    API both still return real data, and reran a full CASE=1/CASE=3
    end-to-end deployment afterward with zero regressions.

12. ~~`exec()`'d model code has no CPU or wall-clock limit - a few bad
    submissions can DoS the executor for everyone.~~ — **done**
    (2026-08-06), same rescan. `mlcode_executor/{tfexecutor,pthexecutor}`'s
    `exec_model()` ran directly in the request-handling thread
    (`sync_to_thread=True` only gets it a worker *thread*, and Python has
    no supported way to forcibly stop a thread stuck in an infinite loop)
    - a handful of concurrent bad submissions could exhaust the whole
    worker pool. Fixed by moving the actual `exec()` + all model-dependent
    work into a `multiprocessing.get_context("spawn")` child process
    (`spawn`, not `fork` - a forked child would inherit this process's
    already-initialized GPU/CUDA context, which TF/CUDA doesn't support
    safely across `fork()`) with a 60s wall-clock cap; on timeout the
    process is `.terminate()`'d then `.kill()`'d if it doesn't exit within
    5s - a real OS process can be forcibly reclaimed, unlike a thread.
    Accepted tradeoff: the child re-imports the whole module (including
    TensorFlow itself) from scratch, adding real per-call latency versus
    the old in-process call - worth it since correctness (a hung
    submission can no longer outlive its timeout) matters more here than
    shaving that off. Verified for real, not just via the existing
    valid-code tests (`uv run pytest`: 8/8 tfexecutor, 7/7 pthexecutor,
    unchanged): submitted a genuine `while True: pass` model to a live
    `TestClient`-backed `/exec_tf/` and confirmed it was killed and
    returned a clean 400 at exactly the 60s timeout, not hung forever.
    **Regression found and fixed (2026-08-06)**: the fix above called
    `process.join(EXEC_TIMEOUT_S)` *before* reading `result_queue`, which
    deadlocks if the child's `put()` payload exceeds the pipe's OS buffer
    (e.g. a real `.h5` model file, easily >64KB) - the child blocks inside
    `put()` waiting for a reader that never comes until `join()` has
    already returned. Reproduced 100% of the time with a real MNIST
    `load_model` call during a full CASE 1-9 regression pass. Fixed in
    both `tfexecutor`/`pthexecutor` by reading the queue (with its own
    timeout) *before* `join()`ing. Also widened the backend's shared
    `httpx.AsyncClient` timeout from the 5s default to 180s
    (`backend/app/main.py`'s `lifespan`) - both executors now spawn a
    subprocess per call that re-imports TensorFlow/PyTorch from scratch
    (~8-10s even for a trivial model), already past the old default,
    which was surfacing as an opaque `httpx.ReadTimeout` -> 500. See
    Critical item 7 above for one call site that had overridden this
    global timeout back down and needed its own follow-up fix.

13. ~~Path traversal / arbitrary file write in
    `mlcode_executor/tfexecutor/app.py`'s `/convert_to_tflite/`.~~ —
    **done** (2026-08-07). Found in the same audit:
    `_convert_model_to_tflite` did `os.path.join('./tmp', filename)` with
    `filename` taken directly from the uploaded file's raw multipart
    `Content-Disposition` filename (the `.h5`-as-field-name wire contract
    - see `mlcode_executor/CLAUDE.md` gotcha 3) - attacker-controlled.
    `os.path.join` discards `'./tmp'` entirely if `filename` is absolute,
    and a relative `../../x` walks out of it either way, so a crafted
    filename could write/overwrite an arbitrary file (the `finally` block
    then deletes whatever path it computed). Compounded by
    `kustomize/base/resources/{tf,pth}-executor-service.yaml` both being
    `type: LoadBalancer` - in a non-local deployment these executors are
    directly internet-reachable, bypassing `backend` and the documented
    exec() threat-model boundary entirely (see the root README's "Threat
    model: exec()'d model code" section - worth a follow-up note there
    that these services shouldn't be given a routable LoadBalancer IP in
    any real deployment, `ClusterIP` is sufficient since only `backend`
    calls them). Fixed by wrapping `filename` in `os.path.basename()`
    before joining, confining the write to `./tmp` regardless of input.
    Separately, `_exec_tf_worker`'s `load_model` branch wrote every
    request's converted model to a fixed `./model.h5` relative to the
    container's shared cwd - concurrent `/exec_tf/` requests (each its
    own subprocess, but sharing that cwd) could interleave and deliver a
    wrong/truncated file to one another. Fixed by using
    `f"model_{os.getpid()}.h5"` (unique per subprocess) instead.

14. ~~`KafkaModelEngine.__getModelWeights__` leaked a `KafkaConsumer`
    every aggregation round~~ (`model_training/tensorflow/
    KafkaModelEngine.py`, byte-identical in `federated-module/
    federated_model_training/tensorflow/KafkaModelEngine.py`) —
    **done** (2026-08-07). Found in the same audit: the loop called
    `consumer.unsubscribe()` but never `.close()`; a fresh `KafkaConsumer`
    is constructed every round inside `EdgeBasedTraining`'s `while rounds
    < training.agg_rounds:` loop, so a long/high-round federated training
    run leaked one socket+thread pair per round, unbounded. Fixed in both
    copies: `consumer.close()` in a `finally` around the read loop, so it
    also runs if an exception interrupts the read (not just on the
    happy-path `break`).

15. ~~`eval()` on user-submitted data runs inside the `backend` API pod
    itself, not an isolated executor.~~ — **done** (2026-08-07).
    `backend/app/utils.py`'s `parse_kwargs_fit` did
    `dic[pair[0]] = eval(pair[1])` on a user-submitted `kwargs_fit`
    string, in the same process that holds live Kubernetes RBAC
    credentials and (when `ENABLE_FEDML_BLOCKCHAIN=1`) the wallet-key
    secret. This was outside the scope the root README's "Threat model:
    exec()'d model code" section describes (executor/training/inference
    pods only, each non-root and capability-dropped per Critical item
    3/High item 10-11 above) - `backend` itself has none of those
    hardenings, since it was never meant to run untrusted code.
    `backend/CLAUDE.md`'s "Things that look like bugs but are
    intentionally preserved for parity" section had documented this as
    deliberate ("not hardened here... this wasn't in scope to change"),
    but that framing predated the executor sandboxing work and
    undersold the actual blast radius difference. Fixed by swapping
    `eval()` for `ast.literal_eval()` - every real `kwargs_fit` value
    (`epochs=5`, `verbose=True`, ...) is a plain literal, never an
    expression that needs full `eval()`, and `literal_eval` can only
    ever produce a literal, not execute arbitrary code. `uv run pytest -v`
    (33/33) still passes.

16. ~~`mlcode_executor`'s multiprocessing timeout/kill escalation ladder
    has zero test coverage of the slow/hanging-code branch~~ — **done**
    (2026-08-07). Added `test_exec_tf_hanging_code_is_killed_within_bounded_time`/
    `test_exec_pth_hanging_code_is_killed_within_bounded_time` to both
    services' test suites - submits a genuine `while True: pass` model,
    with `EXEC_TIMEOUT_S` monkeypatched down from the production 60s (2s)
    so the suite itself stays fast, and asserts the request returns
    `400`/empty body within a bounded wall-clock window (15s, comfortably
    covering the 2s timeout plus both terminate/kill join windows). A
    regression back to the join-before-read deadlock this timeout ladder
    itself once had would now fail this test instead of only surfacing as
    a real cluster hang. `uv run pytest -v`: 9/9 tfexecutor, 8/8
    pthexecutor.

17. ~~Race condition in `federated_backend`'s collision-matching can
    launch duplicate edge worker Jobs even after the "mark consumed"
    fix~~ — **done** (2026-08-07). `app/controllers.py`'s
    select-candidates -> deploy -> mark-consumed section (both
    `create_datasource` and `model_from_control_logger`) now runs inside
    a module-level `asyncio.Lock`, with an explicit `db_session.commit()`
    before releasing it rather than leaving the commit to
    `provide_db_session`'s outer `session.begin()` (a lock alone only
    serializes the in-Python critical section - without committing before
    release, a matched row's delete would still be invisible to the next
    lock-acquirer's own fresh `AsyncSession` until this request's
    transaction actually landed, reopening the same race at the database
    level instead of the event-loop level). **Honest empirical caveat,
    checked directly, not assumed**: a real concurrent-request test
    (`test_concurrent_matching_datasources_only_deploy_once`,
    `AsyncTestClient` + `asyncio.gather`) passes identically with or
    without this fix - each handler's own `db_session.add(...)` + `await
    db_session.flush()` (a real write) happens before the match section,
    and SQLite only allows one writer transaction at a time, so a second
    concurrent request's own flush already blocks on the first request's
    uncommitted write until it fully finishes - the interleaving the
    original finding described can't actually occur against this
    SQLite-backed deployment as it stands today. The lock + early-commit
    are kept anyway: they make the critical section correct on its own
    logical merits rather than incidentally-correct because of SQLite's
    single-writer behavior, and would matter if this service's storage
    backend ever changed to something with real concurrent writers (e.g.
    Postgres). `uv run pytest -v` (15/15) passes.

18. ~~Deploying a PyTorch model with "Federated learning" checked doesn't
    error - it silently does plain, non-federated training while the
    deployment is labeled and tracked as federated~~ — **done**
    (2026-08-07). Fixed on three levels: (1) `frontend/src/logic/
    deployment.ts`'s `isDeploymentFormInvalid` now rejects
    `form.federated && hasPth`; (2) `DeploymentView.tsx` hides the
    "Federated learning" checkbox entirely when the configuration
    contains a PyTorch model, matching the same pattern the distributed
    checkbox in `ModelView.tsx` already used; (3) `backend/app/
    controllers/deployments.py`'s `create_deployment` rejects
    `federated=True` + any PyTorch model in the configuration with a
    clear `400`, server-side, before ever reaching the Job-creation loop
    - defense in depth for anyone calling the API directly, not just
    through the UI. `uv run pytest -v` (34/34, new
    `test_federated_deployment_with_pytorch_model_is_rejected`), `pnpm
    typecheck`, `pnpm test:run` (99/99, new frontend test), `pnpm build`,
    and `pnpm test:e2e` (3/3) all pass.

19. ~~IoT/TFLite deploy (`POST /results/inference-iot/{id}`) always failed
    model conversion for every TensorFlow result~~ — **done** (2026-08-07,
    found by a full build+deploy+real-training regression pass, not a
    pre-existing known issue). `backend/app/controllers/iot_devices.py`
    posts the model via httpx as `files={f"{result_id}.h5": model_bytes}`
    - a bare `bytes` value, not a `(filename, content)` tuple. httpx's
    `FileField` only uses the dict key as the multipart field *name*; for
    a bare-bytes value with no `.name` attribute it falls back to a
    literal filename of `"upload"` (confirmed via `httpx/_multipart.py`'s
    own source, not assumed). `mlcode_executor/tfexecutor/app.py`'s
    `convert_to_tflite` correctly matched the upload by field name
    (`name.endswith('.h5')` - this field-name-is-the-filename contract is
    intentional and documented in `mlcode_executor/CLAUDE.md`'s Gotcha 3),
    but then called `_convert_model_to_tflite(model_bytes,
    model_file.filename, ...)` - using the never-set `.filename`
    ("upload") instead of the field name it had already matched on. Keras
    3's `load_model` can't format-detect an extensionless path, so every
    real IoT deploy failed with `File format not supported: filepath=./
    tmp/upload`. The existing test (`test_convert_to_tflite_no_
    quantization_returns_flatbuffer`) never caught this because it
    happens to pass an explicit `("42.h5", ...)` tuple, which does carry
    a filename - it tests a shape the real backend never actually sends.
    Fixed by using the matched field name throughout instead of
    `model_file.filename`; added
    `test_convert_to_tflite_matches_backends_actual_upload_shape`, which
    replicates the backend's real bare-bytes request shape so this can't
    silently regress again. `uv run pytest` (10/10) passes; verified live
    against the real deployed cluster too - `POST /results/inference-iot/2`
    against a real finished CASE=1 result now returns `200` and produces
    a real `.tflite` file (confirmed via `kubectl exec` into the backend
    pod), not just a passing unit test.

### Medium

1. ~~`federated-module/` duplicates the main backend~~ — **evaluated
   (2026-08-04), recommendation: don't merge.** Read both codebases side
   by side before concluding, rather than going on the directory
   structure alone: `federated_backend` has exactly 2 models
   (`ModelSource`, `Datasource` - both denormalized snapshots shaped for
   `check_colission()`'s comparison, not full domain objects) and 2
   endpoints (`/federated-datasources/`, `/model-control-logger/`).
   `backend` has 7 models and 7 controller modules covering the entire
   platform CRUD surface (models, configurations, deployments, results,
   inferences, datasources, IoT devices). The actual overlap is much
   narrower than "duplicates the main backend" suggests - `federated_
   backend` doesn't reimplement any of that CRUD surface at all; it's a
   small (587-line), purpose-built collision-matching orchestrator with
   its own lifecycle (separate `federated-kafkaml` ServiceAccount/
   namespace subtree already). The one real duplicated *bug* found across
   both (a bare `client.Configuration()` discarding the in-cluster
   default - see `backend/CLAUDE.md` bug #9 and `federated-module/
   CLAUDE.md`'s `federated_backend/` bug #3) is now independently fixed
   in both, and can't be shared as a common utility without either backend
   importing from the other (`kubernetes_asyncio` vs. sync `kubernetes`,
   Litestar vs. Django, Python 3.12 project boundaries that are
   deliberately separate deployable units) - not worth the coupling for
   two ~3-line functions. Merging would mean the actively-deployed main
   backend absorbing federated-specific collision-matching and Job-
   creation concerns it doesn't otherwise have, for a marginal DRY win on
   a service that's small, working, and cleanly isolated today - a step
   backward on separation of concerns, not forward. No code changes as a
   result of this evaluation.

2. ~~`examples/*/requirements.txt` pin old, unaudited versions per example~~
   — **done** (2026-08-06). All 9 examples were pinned to `tensorflow==2.7.0`
   (Oct 2021, EOL) and `kafka-python==3.0.9` - one patch behind the
   `3.0.10` every other project in this repo already uses. Bumped to the
   same versions already verified elsewhere in this repo rather than just
   "latest": `tensorflow==2.21.0` + `numpy==2.4.6` (the pairing
   `model_training/tensorflow`/`model_inference/tensorflow`/
   `mlcode_executor/tfexecutor` already established - `numpy` 2.5.x isn't
   compatible with this `tensorflow` version), `tensorflow-datasets==4.9.10`
   (matches `mlcode_executor/tfexecutor`), `kafka-python==3.0.10` (matches
   `datasources`/`model_training/tensorflow`), `scikit-learn==1.9.0` (matches
   `model_training/tensorflow`). `pandas` had no existing pin anywhere else
   in the repo to match - bumped to current `3.0.5`, confirmed by a real
   install (not assumed compatible from version numbers alone). Verified
   with a real `uv venv --python 3.11` + `uv pip install -r requirements.txt`
   for every example (including the local `../../datasources` path
   dependency), plus an import smoke test confirming the exact `tf.keras`
   APIs the scripts call (`datasets.mnist.load_data`,
   `datasets.cifar10.load_data`, `utils.to_categorical`) still exist in
   2.21.0. New `.github/workflows/examples.yml` (matrix over all 9
   directories) now runs this same install + a generic
   `examples/check_imports.py` on every push/PR touching `examples/**` or
   `datasources/**` - it AST-parses each example's own `.py` files for their
   real `import`/`from` statements and confirms each resolves, rather than a
   hand-maintained parallel dependency list that would itself go stale.
   Does **not** actually run the scripts - they open a live
   `KafkaProducer`/`KafkaConsumer` immediately at import time
   (`kafka-python` connects eagerly in the constructor) with no broker
   available in CI, the same "impractical to reproduce in CI" call already
   made for the 9-CASE dispatch itself (see Critical item 4 above).
   **Found a real, pre-existing bug the first time this CI check ran**:
   `HCOPD_Avro_format`'s `requirements.txt` never declared `pandas` or
   `scikit-learn` at all, despite both scripts importing them
   (`HCOPD_data_stream_producer.py`/`HCOPD_inference.py` use
   `pandas`/`sklearn.preprocessing`) - anyone following that example's
   README would have hit a bare `ModuleNotFoundError` on the very first
   run, unrelated to any version staleness. Not something the version-pin
   audit above would have caught by itself (the file installed "cleanly" -
   it was just missing entries). Fixed by adding both, confirmed via a
   real `gh workflow run` (not just the local venv test) before and after.
   The same real CI run then caught a second, identical-shaped bug:
   `MLGPARK_STREAM_RAW_format`'s `requirements.txt` was missing `pandas`
   (imported by `MLGPARK_dataset_training_example.py`) and `urllib3`
   (`MLGPARK_dataset_inference_example.py` calls `urllib3.PoolManager()`
   directly - it happens to already be pulled in transitively via
   `tensorflow`'s own `requests` dependency today, but declaring it
   explicitly is the whole point of this audit, not relying on another
   package's dependency tree to keep providing it by accident). After both
   fixes, cross-checked all 9 examples' actual `import`/`from` statements
   against their `requirements.txt` directly (AST-parsed, same technique
   `check_imports.py` uses) to confirm no third instance of this same gap
   existed before calling this item done.

3. ~~README GPU section is stale.~~ — **done** (2026-08-06). The "GPU
   configuration" section used to walk through installing Aliyun's
   `gpushare-scheduler-extender`/`gpushare-device-plugin` and a manual
   `kubectl label node ... gpushare=true` step - replaced with the
   official NVIDIA Container Toolkit + NVIDIA device plugin install
   (`nvidia.com/gpu` as an auto-discovered allocatable resource, no
   manual node labeling). Confirmed this is the resource name Kafka-ML's
   own backend already requests - `gpumem` in a deployment/inference
   payload becomes `resources.limits["nvidia.com/gpu"]`
   (`backend/app/controllers/deployments.py:264`, `inferences.py:228`) -
   so the doc now accurately matches what the code actually does, not
   assumed from the changelog alone. Added a step pointing at the
   `-gpu` kustomize overlays too, which the old section never mentioned
   at all.

4. ~~No CONTRIBUTING.md, issue templates, or PR template.~~ — **done**
   (2026-08-06): `CONTRIBUTING.md`, `SECURITY.md`,
   `.github/ISSUE_TEMPLATE/{bug_report,feature_request}.yml` +
   `config.yml`, `.github/pull_request_template.md` added.
   `.github/CODEOWNERS` also added, but as an inert template (commented
   out) - real GitHub usernames/teams for each area aren't knowable from
   inside the repo, and fabricating ownership assignments would be worse
   than leaving it unfilled (GitHub just ignores CODEOWNERS lines whose
   user/team isn't a real collaborator, so an unfilled file breaks
   nothing - it just doesn't auto-assign reviewers yet). A repo admin
   needs to fill in real owners for it to actually do anything.

5. ~~`web3==5.28.0` (backend, model_training/tensorflow,
   federated_model_training/tensorflow) is 3 major versions behind, and
   is the root cause of several existing workarounds, not just its own
   staleness.~~ — **done** (2026-08-05), bumped to `web3==7.16.0` as its
   own dedicated pass with full CASE=9 re-verification, exactly as this
   item called for. All three flagged workarounds are gone: the
   `protobuf` override (`uv lock` now resolves `protobuf` to the same
   version `tensorflow==2.21.0` already needs, confirmed empirically,
   zero override needed anywhere); the `setuptools<81` pin (7.x has no
   `pkg_resources` import); the `inspect.getargspec = inspect.getfullargspec`
   shim in all three files (7.x's `eth-abi`/`parsimonious` don't touch
   `inspect.getargspec` at all). The real cost of the bump was v6's
   camelCase->snake_case rename of nearly every Eth JSON-RPC method
   (`toChecksumAddress`, `getTransactionCount`, `defaultAccount`,
   `buildTransaction`, `signTransaction`, `sendRawTransaction`,
   `waitForTransactionReceipt`, `Web3.toWei`,
   `SignedTransaction.rawTransaction`) - updated everywhere they're
   called (`backend/app/blockchain.py`,
   `model_training/tensorflow/blockchain_utils.py` and
   `blockchainSingleFederatedTraining.py`,
   `federated-module/federated_model_training/tensorflow/federated_blockchainSingleClassicTraining.py`).
   `TxReceipt.contractAddress` and every contract *ABI* function name
   (`contract.functions.saveTrainingSettings(...)` etc.) were correctly
   left alone - neither is web3.py API, both come from the raw Ethereum
   JSON-RPC response / the deployed Solidity contract itself. Verified
   with a full CASE=9 MNIST run (5 real on-chain federated rounds against
   the local Anvil devnet, real ERC20 token + `FederatedLearning.sol`
   deployment, real reward transfer), reaching `accuracy: 1.0` with zero
   duplicate Jobs. See `backend/CLAUDE.md` bug #12 and
   `model_training/tensorflow/CLAUDE.md`'s "web3 5.28.0 -> 7.16.0"
   section for the full record.

6. ~~`federated_backend` (Django) is now the only non-Litestar backend
   service.~~ — **done** (2026-08-05): rewritten to Litestar + SQLAlchemy
   async + `kubernetes_asyncio`, as its own dedicated follow-up right
   after the routine dependency-audit pass that first surfaced this item
   (user: "why don't we change it to a litestar" - agreed to scope it
   separately given this service is the exact matching/deploy logic every
   CASE 5-9 federated test depends on). Done in the same pass: High item 9
   above (mark-consumed) and a real, precise fix for the "replay on
   restart" bug (`federated_model_control_logger.py`'s
   `auto_offset_reset='earliest'`, previously only described here as an
   observed symptom, not a pinned-down cause). Verified via 14 ported
   tests plus real CASE 5/6/7/9 re-runs against the live cluster, zero
   duplicate Jobs across two separate service restarts. See
   `federated-module/CLAUDE.md`'s "federated_backend/ — Django→Litestar
   rewrite" section for the full record.

7. ~~`datasources` and `kafkaml-client` (the two pip-installable Python
   libraries in this repo) had zero test coverage and no CI job.~~ —
   **done** (2026-08-06). `datasources` (43 tests): `KafkaConsumer`/
   `KafkaProducer` faked via a `patch_kafka` fixture (constructing any
   `Sink` talks to Kafka immediately, so there's no way to unit-test the
   pure encoding/control-message-shape logic without replacing them
   first) - covers the deployment-id-above-255 encoding fix, every
   Sink subclass's auto-detect-format-on-first-send behavior (and the two
   that deliberately *don't* auto-detect -
   `OnlineFederatedRawSink`/explicitly-pre-configured `OnlineRawSink`),
   and a real `fastavro` encode/decode round trip for `AvroSink`/
   `AvroInference` (not mocked - the whole point of those classes is the
   schema-bound serialization). `kafkaml-client` (23 tests): a small
   in-memory fake backend wired in via `httpx.MockTransport` (httpx's own
   supported way to test client code) - covers the id-lookup-after-create
   logic every create method needs (the backend's own create endpoints
   return no body), the before/after id-diffing `create_deployment`/
   `deploy_inference` use instead, error wrapping into `KafkaMLError`, and
   `wait_for_results`' polling/timeout behavior. Both pinned
   `pytest==8.4.2`, not the `9.x` every service project in this repo
   already uses - `9.x` dropped Python 3.9 support, and unlike a
   single-Docker-environment service, these two packages' own
   `requires-python = ">=3.9"` is a real compatibility promise to
   whatever Python version installs them. New `.github/workflows/
   {datasources,kafkaml-client}.yml` (test-only, no Docker image to
   build/push for either).

8. ~~`stop_inference` swallows Kubernetes errors and marks the row
    "stopped" regardless.~~ — **done** (2026-08-06, fresh-eyes rescan -
    see Critical items 5-6/High items 10-12 above for the rest of this
    pass). A bare `except Exception: pass` around the RC-delete call in
    `backend/app/controllers/inferences.py` was followed unconditionally
    by `inference.status = "stopped"` - a transient K8s error left the
    real workload running forever, now unreachable via the API (`stop`/
    `delete` key off a status this call already overwrote). Fixed: only a
    404 (`ApiException.status == 404`, meaning the RC is already gone) is
    treated as success; every other `ApiException` now raises a 502
    instead of lying about the outcome. New `tests/test_inferences.py`
    (2 tests: 404 → marked stopped, 500 → stays "deployed" and the caller
    gets a real error) - `uv run pytest` 32/32.

9. ~~A partial Kubernetes failure orphans already-created training Jobs
    outside the DB transaction.~~ — **done** (2026-08-06), same rescan.
    `create_deployment` wraps one DB transaction around a loop that
    creates one real Job per root model - if job N+1 failed, the
    transaction rolled back (Deployment/TrainingResult rows deleted) but
    job N was already running for real against a `RESULT_URL` that no
    longer existed. Fixed by tracking `created_job_names` and, on a later
    failure, best-effort deleting every already-created Job via a fresh
    Kubernetes client before re-raising the original error (a cleanup
    failure is logged, not re-raised - the caller still sees the real
    error, not a masked one). New `tests/test_deployments.py` (seeds a
    real 2-model configuration, mocks the second `create_namespaced_job`
    call to fail, asserts `delete_namespaced_job` was called exactly once
    for the first model's Job) - `uv run pytest` 33/33. **Also found and
    fixed a real, unrelated, genuinely intermittent bug in
    `tests/conftest.py` while adding this test**: `Base.metadata` only
    gets populated with table definitions once `app.models` has actually
    been imported somewhere, and the schema-creation fixture could
    previously run before anything had done that, depending on which
    subset of test files pytest happened to collect - `test_configurations.py`/
    the new `test_deployments.py` never import model classes directly
    (they only ever go through the REST API), so a selection of just
    those collected an empty `Base.metadata` and every DB-touching call
    failed with `no such table`. Fixed by importing `app.models`
    explicitly in `conftest.py` itself. Confirmed fixed by stress-testing
    the previously-failing file combination 5 times in a row (previously
    reproduced 100% of the time) plus 5 full-suite runs, all clean.

10. ~~Model-download HTTP calls have no timeout - can hang forever on the
    very first attempt.~~ — **done** (2026-08-06), same rescan.
    `urllib.request.urlopen(model_url)` (`model_training/tensorflow`,
    `model_inference/tensorflow`) and `requests.get(model_url)`
    (`model_training/pytorch`, `model_inference/pytorch`) had no
    `timeout=` - if the backend accepted the connection but stalled
    mid-response, the call blocked indefinitely and the existing
    `RETRIES`/`SLEEP_BETWEEN_REQUESTS` retry loop never even engaged.
    Fixed with `timeout=30` on all 4 call sites (`socket.timeout` is a
    subclass of `OSError`/`Exception`, already caught by each function's
    existing retry handler, so no other change was needed).

11. ~~Every retried result upload leaks a file handle.~~ — **done**
    (2026-08-06), same rescan. `mainTraining.py`'s `sendSingleMetrics`/
    `sendDistributedMetrics` opened the trained-model (and, for the
    distributed case, one file per submodel) with a bare `open(...)`
    inside their retry loop and never closed any of them - up to
    `RETRIES` (10) leaked file descriptors per pod per result on a flaky
    backend connection. Fixed with a `with open(...) as ...:` block for
    the single-model case and `contextlib.ExitStack` for the
    variable-length distributed case (closes every file it opened
    regardless of how many submodels there are). Verified for real, not
    just via existing tests (none covered this code path): ran real
    CASE=1 and CASE=3 end-to-end deployments against the live cluster
    after rebuilding the image, both reached `status: "finished"` with
    real metrics posted back correctly.

12. ~~Labels above 255 still crash the data sink.~~ — **done**
    (2026-08-06), same rescan, fixed by widening as requested rather than
    just documenting the ceiling. `KafkaMLSink.__object_to_bytes`'s `int`
    branch did `bytes([value])` - a single byte, raising `ValueError` for
    any value outside 0-255 and unable to represent a negative value at
    all. This is reachable in practice only via the base `KafkaMLSink`
    class used directly (every real `RawSink`/`OnlineRawSink`/
    `FederatedRawSink`/`OnlineFederatedRawSink` already converts labels to
    `bytes` via numpy's own `.tobytes()` before this method ever sees
    them, which already correctly handles any dtype width - confirmed by
    reading every subclass's `send()`, not assumed). Widened `int`
    specifically (kept `bool` as its own single-byte case - it was never
    broken) to a fixed 4-byte **little-endian** encoding - deliberately
    the opposite endianness from the neighboring
    `__deployment_id_to_bytes` (that one's bytes are decoded by a plain
    Python `int.from_bytes(..., "big")` consumer; these bytes are decoded
    via `tf.io.decode_raw`, which defaults to little-endian and nothing in
    this codebase overrides that - confirmed with a real round-trip
    through the actual `model_training/tensorflow/utils.py:decode_raw`
    function before trusting the choice, not assumed from symmetry with
    the deployment-id fix). Existing parametrized test updated for the
    new 4-byte output; new test cases added for values >255, >65535, and
    negative values, each confirmed to actually reach `sink.send()`
    successfully now. `uv run pytest` 46/46 in `datasources`.

13. ~~The `-gpu` PyTorch images build and push successfully while silently
    shipping CPU-only torch on a CUDA base.~~ — **done** (2026-08-06),
    same rescan, across all three affected services
    (`model_training/pytorch`, `mlcode_executor/pthexecutor`,
    `model_inference/pytorch`). `uv sync --locked` always installs the
    *lockfile's* torch/torchvision - CPU-only, since `uv.lock` is resolved
    against the `pytorch-cpu` index pinned in `pyproject.toml`'s
    `[tool.uv.sources]` regardless of `BASEIMG` - so every published
    `-gpu` image quietly never used the GPU. Fixed with a new
    `TORCH_VARIANT` build arg: when set to `gpu`, the Dockerfile
    reinstalls both packages from the plain PyPI index after `uv sync`
    (confirmed via PyPI's own JSON API that its Linux `torch==2.13.0`
    wheel is 526MB, consistent with a CUDA-bundled build, not the ~200MB a
    CPU-only wheel would be), and all three `-gpu` CI matrix entries now
    pass `TORCH_VARIANT=gpu` alongside `BASEIMG`. Verified with a real
    local build + run, not just reading the Dockerfile: the build log
    itself showed `- torch==2.13.0+cpu` / `+ torch==2.13.0` /
    `+ triton==3.7.1` (Triton is CUDA-only, never a CPU-build dependency),
    and running the resulting image showed `torch.__version__ ==
    '2.13.0+cu130'` / `torch.version.cuda == '13.0'` versus the untouched
    default build's `'2.13.0+cpu'` - confirming this is a genuine
    CUDA-enabled build, not just a relabeled CPU one. The default
    (non-GPU) build path is unaffected - confirmed the conditional
    correctly no-ops in ~0.2s when `TORCH_VARIANT` isn't set to `gpu`.

14. ~~Three services get zero CI feedback on a pull request.~~ — **done**
    (2026-08-06), same rescan. `kafka_control_logger.yml`/
    `federated_data_control_logger.yml`/`federated_model_control_logger.yml`
    had no `pull_request:` trigger at all, unlike every other
    Dockerfile-building workflow. Adding the trigger alone wasn't enough,
    though - none of these three has a `test` job either (all three
    services are small scripts with everything inline under
    `if __name__ == '__main__':`, nothing factored out to unit-test, per
    Critical item 4's note above), and their `build-*` job had no PR
    gate, so a naive fix would have made a PR try to build *and push* an
    image. Fixed properly: added `pull_request:` triggers, gated the
    existing `build-*` job behind `if: github.event_name !=
    'pull_request'` (matching every sibling workflow), and added a new
    PR-only `test-build` job that does a real `docker build` with
    `push: false` - a genuine, meaningful check (catches a broken
    Dockerfile or an unresolvable dependency) without needing registry
    credentials. Verified all three Dockerfiles actually build clean
    locally (proving the new job would give real, not just theoretical,
    feedback) and that the YAML itself parses correctly.

15. ~~No dependency or container-image vulnerability scanning anywhere in
    CI.~~ — **done** (2026-08-07). Grepped every `.github/workflows/*.yml`
    - Dependabot only opened version-bump PRs, never scanned for known
    CVEs in what was currently pinned; no `trivy`/`grype`/`pip-audit`/
    `npm audit`/CodeQL/`dependency-review-action` job existed anywhere.
    With 10+ services each pinning their own dependency set (16
    independent `uv.lock` files plus `frontend`'s and `website`'s
    `pnpm-lock.yaml`), a known-CVE package could sit unnoticed
    indefinitely between manual audits (see Low item 2's now-obsolete
    `npm audit` note - nothing had replaced it as an ongoing check).
    Fixed with a new `.github/workflows/security-scan.yml` running
    [OSV-Scanner](https://google.github.io/osv-scanner/) - one tool
    across both ecosystems already in use here (reads `uv.lock` and
    `pnpm-lock.yaml` directly with `--recursive`, no per-ecosystem tool
    needed) rather than wiring up separate `pip-audit`/`pnpm audit` jobs.
    Runs on push/PR (SARIF results uploaded to code scanning via the
    official reusable workflow) plus a weekly `schedule` trigger, so a
    CVE disclosed *after* a dependency was already pinned still gets
    caught without needing a new push.

16. ~~No React `ErrorBoundary` anywhere in `frontend/src`~~ — **done**
    (2026-08-07). Grepped, zero matches beforehand. Several list-view
    cell renderers do unguarded field access (e.g. `ResultList.tsx`'s
    status-icon lookup keyed by `row.original.status`) that can throw on
    an unexpected payload shape; with no boundary anywhere in the tree,
    React 19 unmounts the *entire* app on any such throw, rather than
    degrading just the one broken view. Distinct from the already-fixed
    `CodeEditor`/`DeploymentList`/`PlotView` bugs (see the
    `` `frontend`-specific follow-ups `` section below) - this was the missing structural
    backstop for whatever the *next* one turns out to be. Fixed with a
    new `src/components/ErrorBoundary.tsx` (a class component -
    React has no hook equivalent for catching render errors), wrapping
    `Layout.tsx`'s `<Outlet/>` and keyed by `location.pathname` so
    navigating away from a crashed view resets the boundary instead of
    leaving the user stuck on the fallback UI. `pnpm typecheck`, `pnpm
    test:run` (98/98), and `pnpm build` all pass clean.

17. ~~`backend` is stuck on Python 3.12 while 7 sibling
    `python:3.12-slim` services successfully moved to 3.14~~ — **done**
    (2026-08-07). `sqlalchemy==2.0.36`'s typing internals used to raise
    `TypeError: descriptor '__getitem__' requires a 'typing.Union' object
    but received a 'tuple'` on Python 3.14, hit while importing
    `app/models.py`'s `Mapped[...]` annotations - not a test-only issue,
    the app wouldn't boot. Confirmed empirically (a real `uv sync
    --python 3.14` + `uv run pytest`, not assumed from a changelog) that
    `sqlalchemy==2.0.51` fixes it - bumped both `backend/pyproject.toml`
    and `federated-module/federated_backend/pyproject.toml` (the exact
    same bug, independently confirmed there too), `requires-python` to
    `>=3.12,<3.15` in both, and both `Dockerfile`s to `python:3.14-slim`,
    matching the other 7 services. `uv.lock` regenerated for both, real
    `.venv` confirmed running actual Python 3.14.6, full pytest suites
    (33/33 backend, 14/14 federated_backend) pass.

18. ~~`website/`'s `typescript` pin is stuck at `~6.0.2` while `frontend/`
    moved to `~7.0.2` cleanly~~ — **done** (2026-08-07). TypeScript 7
    removed the `baseUrl` compiler option entirely
    (`error TS5102: Option 'baseUrl' has been removed`), and
    `website/tsconfig.json` extended `@docusaurus/tsconfig@3.10.2`, which
    still sets `baseUrl` in its own file - not editable from this repo.
    Confirmed the exact failure mode empirically first (a scratch copy
    with `typescript` bumped alone fails on the *inherited* `baseUrl`,
    not just the local one) before concluding it needed more than a
    version bump. Fixed by dropping the `extends` entirely and inlining
    the handful of options this project actually needs from
    `@docusaurus/tsconfig` directly into `website/tsconfig.json`, using
    `"paths": {"@site/*": ["./*"]}` instead of `baseUrl` - confirmed
    against `@docusaurus/tsconfig@3.10.2`'s own file, not guessed.
    `@docusaurus/tsconfig` dropped from `devDependencies` (nothing else
    referenced it). `pnpm typecheck` and `pnpm build` both verified clean
    on the real `typescript@7.0.2` install, not just a scratch copy.

19. ~~Blocking synchronous file I/O in async route handlers, on a
    single-worker event loop~~ — **done** (2026-08-07).
    `backend/app/controllers/training_results.py` (two call sites) and
    `iot_devices.py` called `.read_bytes()` directly inside `async def`
    handlers - unlike `mlcode_executor`'s own `_convert_model_to_tflite`,
    which explicitly offloads equivalent work via `anyio.to_thread.
    run_sync` for exactly this reason. Fixed all three call sites the
    same way - a large model file read no longer stalls the single
    event loop (including the live `/ws/` relay) for its duration. `uv
    run pytest -v` (33/33) still passes.

20. ~~`model_training/pytorch`'s helper functions (`download_model`,
    `select_gpu`, `load_environment_vars`, etc.) have zero test
    coverage~~ — **done** (2026-08-07). Added `tests/test_training.py`
    (select_gpu's nvidia-smi-parsing/missing-binary branches,
    load_environment_vars' env-var parsing including a missing-required-
    var failure case, split_fit_params/split_val_params' ignite-kwarg
    bucketing) and `tests/test_utils.py` (download_model's success,
    retry-then-succeed, and retries-exhausted-returns-None paths) - 13
    new tests, all against mocked `subprocess`/`requests`/`os.environ`,
    no real Kafka/cluster needed, matching the existing
    `test_training_kafka_dataset.py`'s isolation approach. `uv run
    pytest -v` (16/16) passes.

21. ~~`website/docs/security.md`'s "Mitigations in place" list is
    stale~~ — **done** (2026-08-07). Added the two missing mitigations
    (the `mlcode_executor` multiprocessing+60s-timeout sandbox, the
    blockchain wallet key's real Kubernetes Secret) plus two more that
    shipped the same day this item was found (the exec()'d-code queue-
    deadlock fix, `ast.literal_eval` replacing `eval()` on `backend`'s
    own `kwargs_fit`/`kwargs_val` parsing), and added a new "Not done"
    entry documenting Kafka's plaintext-everywhere transport (see "Not
    planned (short term)"/Medium item 2 above for the underlying,
    still-open code-level finding - this doc update is just the
    disclosure the threat model was missing, not a fix for that item).

22. ~~IoT/TFLite edge deployment is TensorFlow-only end-to-end, but
    nothing tells a user that before they hit a confusing generic
    error~~ — **done** (2026-08-07). `mlcode_executor/pthexecutor` has no
    `/convert_to_tflite/` equivalent, and `backend/app/controllers/
    iot_devices.py`'s `deploy_to_iot_devices` used to unconditionally
    look for `{result_id}.h5` regardless of the result's actual
    framework. Fixed on three levels: (1) backend now eager-loads the
    result's model and returns a clear
    `400 "IoT/TFLite deployment is only supported for TensorFlow
    models."` instead of a generic 404 for a non-TF result; (2)
    `simple_model_dict` (used for every `SimpleModel`-shaped API field,
    including `TrainingResult.model`) now includes `framework`, so the
    frontend can actually know a result's framework without a second
    fetch; (3) `ResultList.tsx`'s "Deploy on IoT" menu item is now
    hidden for non-TF results (same pattern the distributed checkbox in
    `ModelView.tsx` already used), and `InferenceIoTView.tsx` itself
    guards direct URL navigation with a friendly message instead of
    rendering a doomed form. `uv run pytest -v` (33/33, including an
    updated `test_create_distributed_father_child` assertion for the new
    `framework` field), `pnpm typecheck`, `pnpm test:run` (98/98), `pnpm
    build`, and `pnpm test:e2e` (3/3) all pass.

23. ~~The blockchain-traced training feature (CASE=9) has no
    operator/user-facing setup documentation anywhere~~ — **done**
    (2026-08-07). New `website/docs/usage/blockchain-traced-training.md`
    - what's needed (a reachable chain, a funded wallet, the
    `kafkaml-blockchain-credentials` Secret), every `fedml.blockchain.*`
    ConfigMap key with `kustomize/local`'s own values as a worked
    example, how to enable and use it, and a brief note on what actually
    happens on-chain per round. Linked from `federated-learning.md`'s
    existing one-paragraph mention and wired into `sidebars.ts`.
    `pnpm build` confirms no broken links.

### Low

1. ~~`backend/devices/__init__.py` is an empty stub app sitting alongside
   `backend/automl/views/iot_devices.py`.~~ — **obsolete** (2026-08-04):
   moot now that `backend/` is the Litestar port, which has no Django-app
   concept at all; the equivalent IoT-device logic lives in
   `backend/app/controllers/iot_devices.py` with no stub sibling. The old
   Django stub still exists at `../kafka-ml/backend/devices/` if this
   history is ever needed, but it's out of scope to clean up a repo that's
   no longer deployed.

2. ~~`frontend`'s dev dependencies currently report ~12 npm audit
   findings~~ — **obsolete** (2026-08-04): moot now that `frontend` is the
   React/pnpm rewrite - a different dependency tree entirely (see the
   `frontend`-specific follow-ups section below for this rewrite's own
   remaining items). The Vue app these findings were against no longer
   exists in this tree.

3. ~~No syntax highlighting in the model code/imports textareas~~ — **done**
   (2026-07-31): the (now-removed) Vue `frontend` added a Monaco-editor
   field for model imports/code and Tasmota Berry scripts; carried forward
   unchanged into the React rewrite (`src/components/CodeEditor.tsx`).

4. ~~`frontend` only ships PrimeVue's default Lara Light theme~~ —
   **done** (2026-07-31): light/dark toggle added, persisted, applied
   before first paint. Carried forward into the React rewrite (shadcn/
   Tailwind CSS variables + a `dark` class, replacing PrimeVue's
   two-separate-stylesheets approach) - see `frontend/CLAUDE.md`'s
   "Gotchas" item 2 equivalent in its Layout table (`src/theme.ts`).

5. ~~`frontend`'s Docker build sends its entire 486MB `node_modules` to the
   daemon every time.~~ — **done** (2026-08-06, fresh-eyes rescan - see
   Critical items 5-6/High items 10-12/Medium items 8-14 above for the
   rest of this pass). Unlike all 12 other Dockerfile directories in the
   repo, `frontend/` had no `.dockerignore` - its build context is
   `frontend` itself (`frontend.yml`'s `context: frontend`), so the root
   `.dockerignore` never reached it. Added one excluding
   `node_modules`/`dist`/`dist-ssr`/`.git`/the Playwright artifact
   directories. Verified with a real rebuild: reported build-context
   transfer dropped from what a 486MB `node_modules` alone would cost to
   582KB.

6. ~~Bare `except:` used as control flow (not real error handling) in
   several training scripts~~ — **done** (2026-08-07).
   `model_training/tensorflow/mainTraining.py`, both copies of
   `KafkaModelEngine.py`, `model_training/pytorch/training.py`, and
   `federated_mainTraining.py` all used a bare `except:` around either a
   dict-init-or-append pattern (swallowing `KeyboardInterrupt`/
   `SystemExit` along with the expected `KeyError`) or a best-effort
   serialize/deserialize-with-fallback pattern (where the fallback
   itself is intentional, but a bare `except:` still swallowed
   `KeyboardInterrupt`/`SystemExit` unnecessarily). Narrowed each to the
   exception it's actually meant to catch: `except KeyError:` for the
   dict-init-or-append sites (`mainTraining.py`'s `saveSingleMetrics`/
   `saveDistributedMetrics`, `training.py`'s `save_metrics`,
   `federated_mainTraining.py`'s `save_metrics`), `except Exception:` for
   the serialize/deserialize-fallback sites (`KafkaModelEngine.py`'s
   `__parse_model_compile_args`/`__deserialize_compile_args__` in both
   copies) where the broad catch is genuinely intentional and only
   `BaseException` subclasses needed excluding. All five files still
   compile clean.

7. ~~Confusion-matrix generation swallows all exceptions down to an INFO
   log~~ — **done** (2026-08-07). `model_training/tensorflow/
   mainTraining.py`'s `createConfussionMatrix` and `model_training/
   pytorch/training.py`'s equivalent inline block both switched from
   `logging.info` to `logging.exception` (still catching the same broad
   `Exception` - confusion-matrix generation can legitimately fail in
   many different ways depending on the model/data shape, so the catch
   itself wasn't the problem) - a real regression here now logs a full
   traceback at ERROR level instead of an easy-to-miss one-line INFO
   message. `cf_generated` still stays `False` on failure either way, so
   training itself still succeeds without a confusion matrix - only the
   visibility of *why* changed.

8. ~~The release process (workflows trigger on `release: types:
   [created]`) is completely undocumented~~ — **done** (2026-08-07).
   Added a "Releases" section to `CONTRIBUTING.md` documenting the
   process as it actually is: no formal versioning scheme or release
   schedule, a GitHub release is cut whenever a notable feature or big
   change lands on `master`, and every service's CI workflow already
   builds+pushes that service's images tagged with the release version
   when one is cut (on top of the floating tags a regular push already
   produces) since each already triggers on `release: types: [created]`.

9. ~~`website/docs/usage/distributed-models.md` is the one usage page
   missing the "TensorFlow-only" disclaimer its siblings all have~~ —
   **done** (2026-08-07). Added the same "Currently only TensorFlow
   supports X" line `incremental-training.md`/`federated-learning.md`/
   `semi-supervised-learning.md` already have, right after the intro
   paragraph, matching their placement. `pnpm build` confirms no broken
   links.

10. ~~The canonical "getting started" example (`examples/MNIST_RAW_format/`)
    has no PyTorch counterpart, and PyTorch coverage across `examples/`
    is a bare model-code snippet in 4 of 9 example READMEs~~ — **done**
    (2026-08-07). New `examples/MNIST_RAW_format/README.md` (this
    directory had no README at all before) with both the TensorFlow and
    PyTorch model code already established and verified in the root
    README's own quickstart (reused verbatim, not reinvented), plus
    instructions for the directory's existing runnable data-producer
    scripts (framework-agnostic - they stream raw MNIST into Kafka
    regardless of which model consumes it). Also added PyTorch snippets
    to two more examples' READMEs (`HCOPD_Avro_format`,
    `NO2SoftSensor_RAW_format` - both simple `Dense`/`Sequential`
    translations, low risk), bringing PyTorch-documented coverage from
    4 to 7 of 9. **Not done**: `TCN_NILM_RAW_format`'s custom
    dilated-Conv1D/causal-padding TCN architecture would need real
    training-time verification to port correctly (not attempted, real
    risk of a subtly wrong translation going unnoticed) - flag if asked,
    don't assume it's covered; `FEDERATED_MNIST_RAW_format` correctly
    has none, since PyTorch federated training doesn't exist at any
    layer (see `model_training/pytorch/CASE_2_9_PLAN.md`'s Phase 3).

### `frontend`-specific follow-ups

1. ~~No end-to-end tests.~~ — **done** (2026-08-06). `e2e/golden-path.spec.ts`
   (Playwright, `pnpm run test:e2e`, CI via `frontend.yml`) drives the
   real app - real routing, real forms, the real Monaco editor, no
   backend/cluster involved - through create model → create configuration
   → deploy → (simulate a training Job finishing, since no CI runner can
   do that for real) → view real metrics → deploy the result for
   inference, plus two smaller specs (empty-form validation, delete
   flow). Every `/api/*` call is answered by `e2e/mock-backend.ts`, a
   small stateful fake (same spirit as `kafkaml-client/tests`' fake
   backend, for the same reason: a cluster-backed E2E run isn't something
   CI can do). **Found and fixed two real bugs getting this working, not
   just test-authoring friction**: `CodeEditor.tsx` had a genuine
   infinite-render-loop crash ("Maximum update depth exceeded") that a
   real user could trigger by typing multi-line indented code quickly
   enough - a one-shot "did this change come from the editor" flag alone
   still hit it intermittently (~40% of real runs) before landing on a
   value-comparison fix that's actually race-free (see that file's own
   comment for the full mechanism). And `DeploymentList.tsx` crashed
   outright (`Cannot read properties of undefined (reading 'map')`) on
   any deployment payload missing a `results` array - not a real backend
   gap (confirmed `backend/app/schemas/__init__.py` always includes it),
   but the mock backend's own first draft didn't, and the real component
   had no defensive fallback for a shape violation either.

2. ~~No TypeScript~~ — **done**, both in the original Vue rewrite
   (2026-07-31) and carried forward into the React rewrite (2026-08-04) -
   the whole app is typed, gated by `tsc -b` in `pnpm build` and CI.

3. ~~`reactflow` and `@tanstack/react-query` are installed but unused~~ -
   **done** (2026-08-06): both removed. `reactflow` had zero imports
   anywhere in `src/`. `@tanstack/react-query` turned out to be more than
   a dead import - `main.tsx` was mounting a live
   `QueryClientProvider`/`QueryClient` around the whole app even though
   no component anywhere calls `useQuery`/`useMutation` - a real unused
   runtime cost, not just unused code eligible for tree-shaking as the
   original framing assumed. Removed the provider wrapper along with the
   dependency; every view still hand-rolls its own `useEffect` fetch,
   unchanged. `pnpm test:run` (83 tests), `pnpm typecheck`, and `pnpm
   build` all pass clean after removal. Re-add either if a real
   pipeline-topology view or complex loading/error/refetch logic
   eventually justifies it - nothing else depends on them having been
   here.

4. ~~No accessibility pass on the sidebar/theme-toggle shell or on
   Monaco fields~~ — **done** (2026-08-06), verified with a real running
   dev server and Playwright driving actual keyboard `Tab`/`Enter` presses
   (not just static markup review). `Layout.tsx`: added a "Skip to main
   content" link as the first focusable element - **found a real bug
   while verifying it**: a plain `<a href="#main-content">` alone doesn't
   move keyboard focus, only scrolls the viewport, because `<main>` isn't
   natively focusable - confirmed live (`document.activeElement` stayed
   `<body>` after activating it) before fixing with the standard
   `tabIndex={-1}` + `focus:outline-none` technique, then re-confirmed
   focus lands on `<main>` and the next `Tab` correctly continues into the
   page's own content instead of restarting at the top. Also: `aria-label`
   on the nav landmark (`NavLinks`'s `<nav>`, shared by the desktop sidebar
   and the mobile `Sheet`), `aria-expanded`/`aria-controls` wired from the
   mobile hamburger button to the `Sheet`'s real content id, and
   `aria-pressed` on both theme-toggle buttons (icon-only header version
   and the sidebar's text+icon version) - all confirmed via a live DOM
   query, not assumed from the JSX. `CodeEditor.tsx`: added an `ariaLabel`
   prop wired into Monaco's own `ariaLabel` editor option (its hidden
   screen-reader textarea otherwise gets a generic, indistinguishable
   name - confirmed live that `ModelView`'s two instances, "Imports" and
   "Model code", were previously unlabeled and now announce distinctly),
   wired at all 4 real call sites (`ModelView` x2, `InferenceIoTView`,
   `VisualizationView`). `pnpm typecheck`/`test:run` (83 tests)/`build`/
   `test:e2e` (3 tests) all still pass.
   **Found and scoped, not fixed here**: tabbing past the new skip link
   into `ModelList`'s icon-only "Add a model" button surfaced a wider
   pattern - ~19 icon-only `<Button>`s across `ConfigurationList`,
   `DatasourceList`, `InferenceList`, `IoTDeviceList`, `ModelList`,
   `PlotView`, `ResultList`, `VisualizationView` rely on a bare `title`
   attribute alone for their accessible name, no explicit `aria-label`.
   Verified this isn't actually broken (`getByRole('link'/'button', {
   name: <title text> })` resolves correctly per the HTML accessible-name
   spec's title fallback, confirmed live) - but `title` tooltips don't
   reliably show on keyboard focus the way they do on mouse hover across
   browsers, so a sighted keyboard-only user gets no visible affordance
   even though a screen reader announces the name correctly. Out of this
   item's stated scope (sidebar/theme-toggle shell + Monaco specifically)
   and too wide (9 files) to fold in as a drive-by - a mechanical
   `title="X"` → `title="X" aria-label="X"` pass across all ~19 is real
   follow-up work of its own.

5. ~~`PlotView` leaks a blob URL on every refresh and can show a stale
   chart under fast navigation.~~ — **done** (2026-08-06, fresh-eyes
   rescan - see Critical items 5-6/High items 10-12/Medium items 8-14
   above for the rest of this pass). Every `refreshData()` call did
   `URL.createObjectURL(blob)` with no matching `revokeObjectURL` of the
   previous one (unlike `api.ts`'s own `downloadBlob`, which does revoke)
   - a real memory leak. There was also no unmount/id-change `cancelled`
   guard here, unlike every other detail view in the app, so a fast route
   change between two results' chart pages could let an older response
   land after a newer one's and overwrite it with stale data. Fixed both:
   a ref now tracks the last-created blob URL so a later call revokes it
   before creating a new one (plus a dedicated unmount effect that revokes
   whatever's still outstanding when the view is left entirely); the
   mount/id-change effect now uses the same `cancelled` pattern
   `ModelView`/etc. already use, guarding both awaited calls. Verified
   live in a real browser with route-level mocking, not just reasoning
   about the code: (1) navigated to a deliberately slow-responding result,
   then immediately to a fast one - final heading correctly showed the
   second result, confirming the first (now-cancelled) response never
   landed; (2) three full refresh cycles produced 3 `createObjectURL`
   calls and 2 matching `revokeObjectURL` calls for every URL except the
   currently-displayed one - zero leaked; (3) navigating away entirely
   afterward revoked the one still-outstanding URL too. `pnpm typecheck`/
   `test:run` (98 tests)/`test:e2e` (3 tests) all still pass.

6. ~~Monaco adds ~579 kB gzipped as its own lazy chunk - evaluate a
   lighter editor (CodeMirror 6) if it becomes a real problem~~ —
   **evaluated (2026-08-07), decision: keep Monaco, no code change.**
   CodeMirror 6's syntax highlighting is built on Lezer, a proper
   incremental parser - not the regex-based Monarch tokenizer Monaco
   uses. The hand-written Berry grammar this project already has and
   ships (`berryLanguage.ts`, sourced from Berry's own Pygments lexer +
   EBNF grammar, real and verified - see `frontend/CLAUDE.md`'s "Berry
   language support" section) would need a full rewrite as a Lezer
   grammar to move to CodeMirror - a strictly bigger, more error-prone
   lift than what already exists and works, for a single language.
   Visually, CodeMirror 6 also doesn't match Monaco out of the box (no
   minimap, different bracket/suggestion chrome by default) - real
   theming work would be needed to get close, with no guarantee of an
   exact match. Given the one-time cost of a working Berry tokenizer is
   already paid, redoing it in a harder grammar system just to save
   ~579 kB gzipped isn't a good trade. No action taken; revisit only if
   Monaco's size becomes an actual measured problem, not a theoretical
   one.

7. ~~Training-result metric charts (`PlotView`, `ResultCompareView`) and
   the live-streaming regression chart (`VisualizationView`) labeled
   their x-axis starting at 0 instead of 1~~ — **done** (2026-08-07).
   `logic/plot.ts`'s `buildChartData`/`buildComparisonChartData` both
   built `labels` via `Array.from({length}, (_, i) => i)` - the first
   epoch plotted as "0", which nobody trains for. Fixed both to `i + 1`.
   `pnpm typecheck`/`test:run` (99/99, updated label assertions) pass.
   Also added the standard rows-per-page selector (10/25/50/100) to the
   shared `DataTable.tsx`, next to the existing Previous/Next controls -
   every list view (`ModelList`, `ConfigurationList`, `DeploymentList`,
   `ResultList`, `DatasourceList`, `IoTDeviceList`) picks it up for free
   since they all share this one component.
