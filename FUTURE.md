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
cutovers are marked **done** below rather than removed, so the history of
what used to be true here isn't lost. Re-evaluate before acting — some
items may already be stale by the time you read this.

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

6. ~~No dependency update automation.~~ — **done** (2026-08-04):
   `.github/dependabot.yml` now covers every ecosystem in the repo — 16
   `uv` entries (one per `pyproject.toml`/`uv.lock` pair), 1 `npm` entry
   (`frontend`), 13 `docker` entries (one per Dockerfile), and
   `github-actions`, all weekly. `frontend` uses pnpm but that's still the
   `npm` ecosystem value — Dependabot auto-detects the lockfile type per
   directory. (Counts as of the React cutover - was 2 npm/14 docker
   entries before `frontend-react`'s entries merged into `frontend`'s.)

7. **CASE=2 (`SingleIncrementalTraining`) can crash and get stuck
   "deployed" forever if zero streaming data batches arrive before its
   stream timeout.** Found 2026-08-04 while re-running `integration-tests/`
   as a final check after this session's security/CI hardening pass -
   reproduced 3/3 times, confirmed unrelated to any of that work
   (`mainTraining.py` wasn't touched this session; `git log` on the file
   shows nothing since the repo-wide cutover). `model_training/tensorflow/
   mainTraining.py`'s `train_incremental_model` (~line 435) only assigns
   `model_trained = self.model.fit(...)` inside `if len(mini_ds) > 0:` -
   if the streaming Kafka consumer's `get_streaming_kafka_batches`
   generator times out having yielded zero non-empty batches, the
   function falls through to `training_results = {'model_trained':
   model_trained}` with `model_trained` never assigned, raising
   `UnboundLocalError`. The trainer's outer exception handler catches
   this, logs it, and loops back to polling `KAFKA_ML_CONTROL_TOPIC`
   indefinitely instead of exiting - the `TrainingResult` stays
   `"deployed"` forever, and the pod/Job never completes (same symptom as
   the already-known leftover stuck Jobs from earlier manual testing -
   see `project_kafkaml_backend_modernization`-adjacent session memory).
   Root cause of the empty-batches condition itself: a real race between
   `OnlineRawSink`'s first `.send()` call (which fires the online control
   message *and* the first data message essentially back to back) and
   the trainer's Kafka consumer-group join - `integration-tests/
   test_case2_single_incremental.py`'s fixed `time.sleep(15)` before
   creating the sink doesn't actually protect against this, since the
   trainer can't start joining the *data* topic's consumer group until
   *after* it receives the control message, which only fires once the
   test starts sending - by which point the tight, delay-free 10-message
   burst loop in `_send_burst` typically finishes before the consumer's
   join-group round trip completes. `test_case4_distributed_incremental.py`
   hit the identical symptom independently and already bumped its own
   sleep from 15s to 35s (see its own inline comment) but nobody
   went back and applied the same fix to `test_case2`. Not fixed here -
   both the `UnboundLocalError` (a real, pre-existing gap in
   `mainTraining.py`, predates the TF/Keras upgrade entirely - it's a bare
   Python scoping bug, nothing a library version could have caused) and
   the test's timing assumption are out of scope for this session's
   backlog; flagging per this project's "flag pre-existing bugs found
   incidentally, don't silently fix" precedent. `test_case1`/`test_case3`/
   `test_inference`/`test_pytorch_classic` (the non-streaming tests) all
   passed cleanly, confirming the hardening changes themselves introduced
   no regression.

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
   section. Item 7's plain-`mainTraining.py` sibling is still open -
   worth fixing both together if either comes up again, same root design
   flaw in two files.

9. **`federated_backend` never marks a matched `Datasource`/`ModelSource`
   row consumed, and this is worse than originally scoped: restarting
   either `federated_data_control_logger` or `federated_model_control_logger`
   (not just `federated_backend` itself) replays their Kafka consumers'
   entire retained control-topic history, re-forwarding every past
   registration from the *whole session* to `federated_backend` at once.**
   Confirmed **recurring** - the identical set of 7-8 stale registrations
   re-matched and re-spawned duplicate edge worker Jobs on two separate
   restarts, hours apart, in the same session (see `federated-module/
   CLAUDE.md`'s "Worse variant" note). A real fix needs both "mark
   consumed" *and* "don't replay history predating this consumer
   instance's own startup" (e.g. commit offsets, or seek-to-end on
   start). Promoted from Medium/flagged-only to explicitly tracked here
   given it's now confirmed to compound on every routine service
   restart, not just a one-off multi-test-in-one-session artifact.

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

5. **`web3==5.28.0` (backend, model_training/tensorflow,
   federated_model_training/tensorflow) is 3 major versions behind, and
   is the root cause of several existing workarounds, not just its own
   staleness.** Deliberately left untouched during the 2026-08-05
   dependency-audit pass (too much real API-breaking-change risk to
   bundle into a routine bump, given it's exactly what CASE=9's
   blockchain path depends on, freshly re-verified that same session).
   Upgrading to a current stable major would let all of these go away
   together: `backend`'s `protobuf` pin stuck at `3.20.3` (2022-era, web3
   hard-pins `protobuf<4` - `model_training/tensorflow` already needed an
   explicit override to coexist with TensorFlow, `backend` never got one
   since it doesn't need TF); the `setuptools<81` pin (web3 does a bare
   `import pkg_resources`); the `inspect.getargspec = inspect.getfullargspec`
   shim in three files (old `eth-abi` → old `parsimonious` calls the
   Python-3.11-removed `getargspec`). Do this as its own dedicated pass
   with full CASE=9 re-verification afterward, not a drive-by version bump.

6. **`backend` is stuck on Python 3.12 while 7 sibling `python:3.12-slim`
   services successfully moved to 3.14** (2026-08-05 dependency-audit
   pass) - `sqlalchemy==2.0.36`'s typing internals
   (`util/typing.py::make_union_type`) raise `TypeError: descriptor
   '__getitem__' requires a 'typing.Union' object but received a 'tuple'`
   on Python 3.14, hit while importing `app/models.py`'s `Mapped[...]`
   annotations - not a test-only issue, the app wouldn't boot. Confirmed
   empirically (a real failed `pytest` collection, not assumed from a
   changelog) before reverting just this one service back to
   `python:3.12-slim`. Revisit once SQLAlchemy ships a 3.14-compatible
   stable release (2.1 was still beta as of this check - also blocked
   from bumping to for a different reason, no stable release yet).

7. **`federated_backend` (Django) is now the only non-Litestar backend
   service** - `backend` was rewritten to Litestar in an earlier session;
   `federated_backend` was deliberately kept on Django then (small,
   587-line, 2-endpoint satellite service, not proportionate for a full
   rewrite at the time - see Medium item 1 above). Revisited 2026-08-05
   during a routine Django version bump: user confirmed the calculus is
   worth revisiting given `backend`'s already the only other stack, but
   asked to keep it as its own dedicated follow-up rather than bundling
   it into that day's dependency-audit pass, given this service is the
   exact matching/deploy logic every CASE 5-9 federated test depends on
   and a rewrite here needs full re-verification, not a quick swap. Worth
   doing this at the same time as fixing Medium/High item 9 above (the
   never-marks-consumed bug) and dropping the sync `kubernetes` client for
   `kubernetes_asyncio` (matching `backend`'s own approach) while already
   touching this code.

8. **`website/`'s `typescript` pin is stuck at `~6.0.2` while `frontend/`
   moved to `~7.0.2` cleanly** (2026-08-05) - TypeScript 7 removed the
   `baseUrl` compiler option entirely, and `website/tsconfig.json` extends
   `@docusaurus/tsconfig@3.10.2`, which still sets `baseUrl` itself - not
   fixable from this repo (can't edit a third-party package's own
   tsconfig). Revisit once a `@docusaurus/tsconfig` release drops
   `baseUrl` for `paths`.

## Low

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

## `frontend`-specific follow-ups

These are scoped to the current frontend itself (React 19 + shadcn/ui,
cut over from Vue 2026-08-04), called out separately since they're closer
to "next PR" than "someday". Items from the Vue-era version of this list
are marked done/obsolete rather than deleted, per this file's usual
policy.

1. **No end-to-end tests.** The current suite (`pnpm test:run`) is unit
   tests for `src/logic/*.ts` plus a handful of component-level tests with
   the API mocked — solid regression coverage for business logic, but
   nothing exercises a real click-through (create model → configuration →
   deploy → train → infer) against a live or mocked backend. There's ad hoc
   Playwright coverage from manual verification passes (not checked in as a
   repeatable suite/CI job) — worth formalizing once the UI stabilizes.
   Same gap the Vue app had before it; never got formalized there either.
2. ~~No TypeScript~~ — **done**, both in the original Vue rewrite
   (2026-07-31) and carried forward into the React rewrite (2026-08-04) -
   the whole app is typed, gated by `tsc -b` in `pnpm build` and CI.
3. **Feature-parity audit vs. the previous frontend hasn't been done by a
   human yet.** Applies transitively through both rewrites: the Angular→Vue
   audit was never done (noted here since 2026-07-31), and neither has a
   Vue→React one. Each rewrite was verified against the live backend
   (CRUD + WebSocket smoke tests, Playwright passes of the UI) but not
   clicked through screen-by-screen by a person. Not a gate on anything -
   both older implementations are already fully retired (Angular preserved
   at `../kafka-ml/frontend`; Vue not preserved anywhere, see this file's
   intro) - just still worth doing.
4. **Monaco adds ~579 kB gzipped as its own lazy chunk** (only fetched when
   a screen with a code field is visited — see `frontend/CLAUDE.md`'s
   Gotcha #5). Acceptable for now; if it becomes a real problem, evaluate a
   lighter editor (CodeMirror 6) or loading Monaco from a CDN instead of
   bundling it. Same order of magnitude as the Vue app's own ~594 kB figure.
5. **`reactflow` and `@tanstack/react-query` are installed but unused** -
   `reactflow` was requested for pipeline-topology visualization, but no
   current view is actually a topology diagram; `react-query` was
   installed as an option but every view still hand-rolls its own
   `useEffect` fetch, matching the old Vue app's "no state library"
   philosophy. Neither is costing anything today (tree-shaken if truly
   unused, or a small fixed cost) but worth revisiting if a real
   pipeline-topology view gets requested, or if a view's loading/error/
   refetch logic grows complex enough to justify react-query.
6. **No accessibility pass on the sidebar/theme-toggle shell or on
   Monaco fields** — keyboard navigation and screen-reader behavior haven't
   been specifically verified (Monaco in particular is known to need extra
   ARIA wiring for full accessibility).
