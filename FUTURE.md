# Future upgrades

A working list of upgrades for this fork, ordered by severity within each
section. Written from a pass over the whole tree (backend, frontend/
frontend-vue, model_training, mlcode_executor, federated-module, kustomize)
as of 2026-07-31, right after the Angular→Vue frontend rewrite. Re-evaluate
before acting — some items may already be stale by the time you read this.

Severity guide: **Critical** = security/availability risk or actively
breaks correctness guarantees today. **High** = real cost or risk, no active
incident. **Medium** = maintainability/debt, no immediate risk. **Low** =
nice-to-have polish.

## Critical

1. **Backend runs on end-of-life dependencies.** `backend/requirements.txt`
   pins `django==3.2.13` (EOL April 2024) and `djangorestframework==3.11.0`
   (2019). No further security patches ship for these. Upgrade path:
   Django 3.2 → 4.2 LTS → 5.x, DRF to a matching current release, and
   `channels`/`daphne` (currently `3.0.4`/`3.0.2`) to their 4.x counterparts
   for the WebSocket support the Visualization view depends on.

2. **`DEBUG` defaults to `True` and `SECRET_KEY` has a hardcoded fallback.**
   `backend/autoweb/settings.py:23,26` — if `DEBUG`/`SECRET_KEY` env vars
   are ever omitted in a real deployment (easy to do — the kustomize
   manifests set them, but a manual `kubectl apply` of a trimmed-down
   Deployment wouldn't), the backend silently runs in debug mode (leaking
   stack traces, settings, SQL) with a key that's public in this repo's
   history. These should fail closed: refuse to start in production without
   both set, rather than defaulting to the insecure option.

3. **User-submitted model code is `exec()`'d with no sandboxing.** This is
   core to how Kafka-ML works (models are pasted as Python in the Web UI,
   then run by `mlcode_executor/{tfexecutor,pthexecutor}` and
   `model_training/*/utils.py` / `mainTraining.py`), so it's not a "bug" —
   but it means anyone who can reach the backend API has arbitrary code
   execution on the executor/training pods. Worth an explicit hardening
   pass: non-root containers, read-only root filesystem, seccomp/AppArmor
   profiles, NetworkPolicies restricting those pods' egress, and a written
   threat-model note in the README so operators know this tool must not be
   exposed to untrusted users without additional isolation (gVisor/Firecracker
   if that's ever a requirement).

4. **No CI job runs any of the existing test suites.** `backend/automl/test_views.py`
   (252 lines) exists but `.github/workflows/backend.yml` only builds and
   pushes the Docker image — `python manage.py test` never runs. The same is
   true for every other Python service (model_training, model_inference,
   mlcode_executor, federated-module): no workflow executes their code at
   all before publishing an image. `frontend-vue/` is the only component
   with tests wired into CI as of this writeup
   (`.github/workflows/frontend-vue.yml`). Adding a `test` step to each
   existing `*.yml` workflow (mirroring what was just done for
   frontend-vue) is low-effort, high-value.

## High

1. **Two frontends now coexist.** `frontend/` (Angular 9, being retired) and
   `frontend-vue/` (its replacement) both exist, and
   `kustomize/base/resources/frontend-deployment.yaml` still points at the
   Angular image. Decide a cutover date, verify feature parity end-to-end,
   swap the kustomize image reference to `kafka-ml-frontend-vue`, then
   delete `frontend/` and `.github/workflows/frontend.yml`.

2. **Cluster credentials are handled as plaintext freeform input.** The
   Inference deployment form (`results/inference/{id}`) accepts a raw K8s
   `token` and Kafka broker URLs as plain text fields with no secret
   storage, and `kustomize/base/resources/backend-deployment.yaml` documents
   pasting a `cluster-admin`-scoped `KUBE_TOKEN` directly into a Deployment
   env var. Prefer K8s Secret references over inline env values, and scope
   the service account role down from `cluster-admin` to only the verbs/
   resources the backend actually needs (Jobs, Deployments, Services).

3. **Python 3.8 base images across the board.** `backend/Dockerfile`,
   `kafka_control_logger/Dockerfile`, and
   `federated-module/federated_backend/Dockerfile` all pin
   `FROM python:3.8.6` (EOL October 2024). `model_training`/`model_inference`/
   `mlcode_executor` build from `tensorflow/tensorflow:${TFTAG}` or a
   configurable `${BASEIMG}` instead, so audit those tags too before
   assuming they're current.

4. **Kustomize version sprawl.** `kustomize/{v1.0,v1.0-gpu,v1.1,v1.1-gpu,v1.3,
   v1.3-gpu,master,master-gpu,local,base}` — ten near-duplicate manifest sets
   to hand-sync. The GPU scheduling plugin was migrated from Aliyun's
   `gpushare` extension to the NVIDIA official device plugin per the commit
   history, but it's unclear whether the older `v1.0`/`v1.1` folders were
   updated to match or are silently stale. Consolidate with Kustomize
   components/overlays instead of full directory copies, or mark
   unsupported versions clearly in `kustomize/README.md`.

5. **No dependency update automation.** No Dependabot or Renovate config
   anywhere under `.github/`. Given how far behind Django/DRF/channels/
   Python already are (see Critical #1, High #3), this is likely how the
   drift happened — an automated PR bot would catch it going forward.

## Medium

1. **`federated-module/` duplicates the main backend** rather than reusing
   it — its own `federated_backend/{automl,autoweb}`, `manage.py`,
   `Dockerfile`. Any core fix (auth, serializers, model validation) has to
   be applied twice. Worth evaluating whether federated deployment could
   become a mode of the main backend instead of a parallel Django project.

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

1. **`backend/devices/__init__.py` is an empty stub app** sitting alongside
   `backend/automl/views/iot_devices.py`, where the real Tasmota/IoT-device
   logic actually lives. Looks like leftover scaffolding from an in-progress
   refactor — either remove it or document why it's there.

2. **`frontend-vue`'s dev dependencies currently report ~12 npm audit
   findings** (vite/vitest/esbuild/glob transitive chain) — all dev-tooling
   only, no production runtime exposure. Not urgent; will resolve on the
   next routine `npm update` once upstream patches land.

3. ~~No syntax highlighting in the model code/imports textareas~~ — **done**
   (2026-07-31): `frontend-vue` now uses a Monaco-editor field
   (`src/components/CodeEditor.vue`) for model imports/code and Tasmota
   Berry scripts.

4. ~~`frontend-vue` only ships PrimeVue's default Lara Light theme~~ —
   **done** (2026-07-31): light/dark toggle added, persisted, applied
   before first paint.

## `frontend-vue`-specific follow-ups

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
3. **Feature-parity audit vs. the Angular app hasn't been done by a human
   yet** — the rewrite was verified against the live backend (CRUD +
   WebSocket smoke tests, plus a Playwright pass of the new theme/Monaco UI)
   but not clicked through screen-by-screen by a person. Do that pass before
   deleting `frontend/`.
4. **Monaco adds ~594 kB gzipped as its own lazy chunk** (only fetched when a
   screen with a code field is visited — see `CLAUDE.md`'s "Code editor"
   section). Acceptable for now; if it becomes a real problem, evaluate a
   lighter editor (CodeMirror 6) or loading Monaco from a CDN instead of
   bundling it.
5. **No accessibility pass on the new sidebar/theme-toggle shell or on
   Monaco fields** — keyboard navigation and screen-reader behavior haven't
   been specifically verified (Monaco in particular is known to need extra
   ARIA wiring for full accessibility).
