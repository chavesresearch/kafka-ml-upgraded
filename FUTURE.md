# Future upgrades

A working list of upgrades for this fork, ordered by severity within each
section. Originally written from a pass over the whole tree as of
2026-07-31, right after the Angular→Vue frontend rewrite; revisited on
2026-08-04 after the Django→Litestar backend, Flask→Litestar
`mlcode_executor`, and dependency-modernized `model_training`/
`model_inference`/`federated-module`/`datasources` ports were all cut over
into their original directory names (`backend/`, `frontend/`, etc. - the
old implementations now live only in the separate `../kafka-ml` reference
checkout, not in this repo). Items resolved by that cutover are marked
**done** below rather than removed, so the history of what used to be true
here isn't lost. Re-evaluate before acting — some items may already be
stale by the time you read this.

Severity guide: **Critical** = security/availability risk or actively
breaks correctness guarantees today. **High** = real cost or risk, no active
incident. **Medium** = maintainability/debt, no immediate risk. **Low** =
nice-to-have polish.

## Critical

1. ~~Backend runs on end-of-life dependencies (Django 3.2.13, DRF 3.11.0,
   channels/daphne 3.x).~~ — **done** (2026-08-04): `backend/` is now a
   from-scratch Litestar/SQLAlchemy async port (see `backend/CLAUDE.md`) -
   no Django, DRF, or channels dependency remains at all. The old Django
   implementation is preserved for reference at `../kafka-ml/backend` if
   this history is ever needed.

2. **`DEBUG` and `ALLOWED_HOSTS` still default to insecure values.**
   `backend/app/config.py:22,24-28` — `DEBUG` defaults to `True` and
   `ALLOWED_HOSTS` defaults to `["*"]` when the env vars are omitted (the
   kustomize manifests do set them, but a manual `kubectl apply` of a
   trimmed-down Deployment wouldn't). This carried over from the original
   Django settings' fail-open defaults rather than being newly introduced,
   but it's still live in the Litestar port. Unlike the old Django
   version, there's no hardcoded `SECRET_KEY` fallback to worry about
   (Litestar's session model here doesn't need one) - just these two.
   Should fail closed: refuse to start in production without both
   explicitly set, rather than defaulting to the insecure option.

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

## High

1. ~~Two frontends now coexist (`frontend/` Angular + `frontend-vue/`
   Vue).~~ — **done** (2026-08-04): cut over. `frontend/` is now the Vue
   app; the old Angular implementation is preserved for reference at
   `../kafka-ml/frontend`. `kustomize/base/resources/frontend-deployment.yaml`
   points at the Vue image (same image name the Angular build used, so no
   manifest edit was needed - see `frontend/CLAUDE.md`).

2. ~~Cluster credentials are handled as plaintext freeform input.~~ —
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

3. ~~Python 3.8 base images across the board (`backend/Dockerfile`,
   `kafka_control_logger/Dockerfile`,
   `federated-module/federated_backend/Dockerfile` all pinned
   `FROM python:3.8.6`, EOL October 2024).~~ — **done** (2026-08-04): all
   three now build from `python:3.12-slim` as part of their respective
   ports/uv migrations. `model_training`/`model_inference`/`mlcode_executor`
   build from `tensorflow/tensorflow:${TFTAG}` or a configurable
   `${BASEIMG}` instead - audit those tags separately if they come up
   (see each service's own `CLAUDE.md` for the specific versions/reasoning
   already checked).

4. **Kustomize version sprawl.** `kustomize/{v1.0,v1.0-gpu,v1.1,v1.1-gpu,v1.3,
   v1.3-gpu,master,master-gpu,local,base}` — ten near-duplicate manifest sets
   to hand-sync. The GPU scheduling plugin was migrated from Aliyun's
   `gpushare` extension to the NVIDIA official device plugin per the commit
   history, but it's unclear whether the older `v1.0`/`v1.1` folders were
   updated to match or are silently stale. Consolidate with Kustomize
   components/overlays instead of full directory copies, or mark
   unsupported versions clearly in `kustomize/README.md`.

5. ~~No dependency update automation.~~ — **done** (2026-08-04):
   `.github/dependabot.yml` now covers every ecosystem in the repo — 16
   `uv` entries (one per `pyproject.toml`/`uv.lock` pair), 2 `npm` entries
   (`frontend`, `frontend-react`), 14 `docker` entries (one per
   Dockerfile), and `github-actions`, all weekly. `frontend-react` uses
   pnpm but that's still the `npm` ecosystem value — Dependabot
   auto-detects the lockfile type per directory.

## Medium

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

2. **`examples/*/requirements.txt` pin old, unaudited versions per example**
   with nothing in CI verifying they still install or run — likely to
   bit-rot silently until someone tries to follow the README tutorial.

3. **README GPU section is stale.** The "GPU configuration" instructions in
   the root `README.md` still walk through installing Aliyun's
   `gpushare-scheduler-extender`, but the changelog and commit history
   indicate the project moved to the NVIDIA official device plugin
   (see `kustomize/master-gpu`). Update the docs to match.

4. **No CONTRIBUTING.md, issue templates, or PR template.** For a
   research-originated project that already takes outside contributions
   (per the publications list in the README), this is easy friction to remove.

## Low

1. ~~`backend/devices/__init__.py` is an empty stub app sitting alongside
   `backend/automl/views/iot_devices.py`.~~ — **obsolete** (2026-08-04):
   moot now that `backend/` is the Litestar port, which has no Django-app
   concept at all; the equivalent IoT-device logic lives in
   `backend/app/controllers/iot_devices.py` with no stub sibling. The old
   Django stub still exists at `../kafka-ml/backend/devices/` if this
   history is ever needed, but it's out of scope to clean up a repo that's
   no longer deployed.

2. **`frontend`'s dev dependencies currently report ~12 npm audit
   findings** (vite/vitest/esbuild/glob transitive chain) — all dev-tooling
   only, no production runtime exposure. Not urgent; will resolve on the
   next routine `npm update` once upstream patches land.

3. ~~No syntax highlighting in the model code/imports textareas~~ — **done**
   (2026-07-31): `frontend` now uses a Monaco-editor field
   (`src/components/CodeEditor.vue`) for model imports/code and Tasmota
   Berry scripts.

4. ~~`frontend` only ships PrimeVue's default Lara Light theme~~ —
   **done** (2026-07-31): light/dark toggle added, persisted, applied
   before first paint.

## `frontend`-specific follow-ups

These are scoped to the new frontend itself, called out separately since
they're closer to "next PR" than "someday":

1. **No end-to-end tests.** The current suite (`npm run test:run`) is unit
   tests for `src/logic/*.ts` plus a handful of component-level tests with
   the API mocked — solid regression coverage for business logic, but
   nothing exercises a real click-through (create model → configuration →
   deploy → train → infer) against a live or mocked backend. There's ad hoc
   Playwright coverage from manual verification passes (not checked in as a
   repeatable suite/CI job) — worth formalizing once the UI stabilizes.
2. ~~No TypeScript~~ — **done** (2026-07-31): the whole app (`src/**/*.ts`
   and every `.vue` SFC's `<script setup lang="ts">`) is now typed, gated by
   `vue-tsc --noEmit` in `npm run build` and CI.
3. **Feature-parity audit vs. the old Angular app hasn't been done by a
   human yet** — the rewrite was verified against the live backend (CRUD +
   WebSocket smoke tests, plus a Playwright pass of the new theme/Monaco UI)
   but not clicked through screen-by-screen by a person. The directory
   cutover already happened (the old Angular `frontend/` is gone, preserved
   at `../kafka-ml/frontend` if a side-by-side comparison is needed) - this
   audit is still worth doing, just no longer a gate on deleting anything.
4. **Monaco adds ~594 kB gzipped as its own lazy chunk** (only fetched when a
   screen with a code field is visited — see `CLAUDE.md`'s "Code editor"
   section). Acceptable for now; if it becomes a real problem, evaluate a
   lighter editor (CodeMirror 6) or loading Monaco from a CDN instead of
   bundling it.
5. **No accessibility pass on the new sidebar/theme-toggle shell or on
   Monaco fields** — keyboard navigation and screen-reader behavior haven't
   been specifically verified (Monaco in particular is known to need extra
   ARIA wiring for full accessibility).
