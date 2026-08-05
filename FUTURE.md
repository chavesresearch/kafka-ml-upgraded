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
   Django→Litestar rewrite (Medium item 7 below): the new
   `federated_backend` deletes both matched rows right after a successful
   deploy, and `federated_model_control_logger.py`'s
   `auto_offset_reset='earliest'` (the actual, precisely-identified cause
   of the replay - not generic "Kafka replay behavior", confirmed via
   `kubectl logs`) was dropped to match its sibling's correct `'latest'`
   default. Verified via real CASE 5/6/7/9 re-runs across two separate
   service restarts: zero duplicate Jobs both times. See
   `federated-module/CLAUDE.md`'s rewrite section for the full record.

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

7. ~~`federated_backend` (Django) is now the only non-Litestar backend
   service.~~ — **done** (2026-08-05): rewritten to Litestar + SQLAlchemy
   async + `kubernetes_asyncio`, as its own dedicated follow-up right
   after the routine dependency-audit pass that first surfaced this item
   (user: "why don't we change it to a litestar" - agreed to scope it
   separately given this service is the exact matching/deploy logic every
   CASE 5-9 federated test depends on). Done in the same pass: High item 9
   below (mark-consumed) and a real, precise fix for the "replay on
   restart" bug (`federated_model_control_logger.py`'s
   `auto_offset_reset='earliest'`, previously only described here as an
   observed symptom, not a pinned-down cause). Verified via 14 ported
   tests plus real CASE 5/6/7/9 re-runs against the live cluster, zero
   duplicate Jobs across two separate service restarts. See
   `federated-module/CLAUDE.md`'s "federated_backend/ — Django→Litestar
   rewrite" section for the full record.

8. **`website/`'s `typescript` pin is stuck at `~6.0.2` while `frontend/`
   moved to `~7.0.2` cleanly** (2026-08-05) - TypeScript 7 removed the
   `baseUrl` compiler option entirely, and `website/tsconfig.json` extends
   `@docusaurus/tsconfig@3.10.2`, which still sets `baseUrl` itself - not
   fixable from this repo (can't edit a third-party package's own
   tsconfig). Revisit once a `@docusaurus/tsconfig` release drops
   `baseUrl` for `paths`.

9. ~~`datasources` and `kafkaml-client` (the two pip-installable Python
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
5. ~~`reactflow` and `@tanstack/react-query` are installed but unused~~ -
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
6. **No accessibility pass on the sidebar/theme-toggle shell or on
   Monaco fields** — keyboard navigation and screen-reader behavior haven't
   been specifically verified (Monaco in particular is known to need extra
   ARIA wiring for full accessibility).
