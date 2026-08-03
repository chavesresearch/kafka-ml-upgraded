# model_training-upgraded — instructions for AI assistants

Sibling of `../model_training` (kept untouched as reference/rollback),
same pattern as `backend-litestar`/`mlcode_executor-litestar`/
`datasources-package`: a behaviorally faithful port to modern dependency
versions, fixing only what's actually broken by the upgrade - not a
rewrite or a redesign. `../model_training/training.py`-equivalent files in
each subdirectory dispatch on the `CASE` env var (1-9) to one of 9
training modes: single/distributed × classic/incremental, 4 federated
variants, and 1 blockchain-federated variant. **All 9 must keep working**
- this was an explicit, non-negotiable requirement from the user for the
TensorFlow pass, and applies equally to PyTorch.

## Layout

| Path | Status |
|---|---|
| `tensorflow/` | Functionally complete. CASE 1-4 (single/distributed × classic/incremental) verified end-to-end against a live local cluster; CASE 5-9 (federated/blockchain) verified at import/compile level only, by explicit user scoping decision (they need `federated-module`, a separate unported module, running as the edge side - and CASE=9 additionally needs a real Ethereum node). See `tensorflow/CLAUDE.md` for the full verification record, every bug found and fixed, and the reasoning behind each. |
| `pytorch/` | Functionally complete and fully verified end-to-end. Much smaller scope than TensorFlow - this module has **no `CASE` dispatch at all**, only one training mode, and needed almost no dependency-compatibility fixes (avro/ignite/numpy all still work under current versions with zero code changes). One real bug found and fixed via the end-to-end test (a Kafka consumer race in `TrainingKafkaDataset.py`). See `pytorch/CLAUDE.md` for the full record. |

**Status: not yet cut over.** `../model_training` is still what's actually
built/deployed by `kustomize` - this directory isn't referenced by any
manifest yet.

## Ground rules (apply to both `tensorflow/` and, later, `pytorch/`)

1. **Faithful 1:1 port - fix only what's broken by the upgrade.** Don't
   restructure or deduplicate the 9 training-mode classes, even where they
   look repetitive. This was an explicit scoping decision, not laziness -
   the goal is a diffable, low-risk port, not a redesign.
2. **A bug found via real end-to-end testing may still be "broken by the
   upgrade" even if the buggy code is byte-identical to the original.**
   Several bugs found while testing the TensorFlow port (see
   `tensorflow/CLAUDE.md`) were *latent* in the original code - tolerated
   by looser Keras 2/older-library semantics, and only surfaced as hard
   errors once the underlying library was upgraded. Distinguish these
   (in scope: the upgrade is what turned a silent success into a crash)
   from bugs that were already broken and produced wrong-but-non-crashing
   output before the upgrade too (out of scope - e.g. the
   `test()`-method metric-zip-by-position issue noted in
   `tensorflow/CLAUDE.md`, flagged but deliberately not fixed).
3. **Verify empirically, don't assume.** Every dependency-conflict
   resolution, every "does this still work under the new library version"
   question, and every claimed fix in this port was checked by actually
   running the code (an isolated repro script, a real container build, or
   a full end-to-end training run against the live cluster - see "Test
   infrastructure" in `tensorflow/CLAUDE.md` for how that cluster is set
   up and how to seed it), not inferred from reading library changelogs
   or source alone.
4. **Real end-to-end testing catches things import-checks can't.** The
   TensorFlow pass found a live cross-service bug this way (a
   `backend-litestar` HTTP status-code mismatch causing an infinite
   client-side retry loop - fixed in `backend-litestar`, documented in
   `tensorflow/CLAUDE.md`) that no amount of reading the training
   container's own code in isolation would have surfaced.

## PyTorch - what actually happened, for calibration next time

Turned out to be a much smaller job than the ground rules above might
suggest, worth knowing in advance if a similar module ever needs this same
treatment: **no `CASE` dispatch, one training mode, and almost nothing
was actually broken by the dependency bump** - `avro`, `pytorch-ignite`,
and `numpy` all still worked completely unchanged against current stable
releases, verified by direct import/signature checks in a scratch venv
before assuming a swap (e.g. `fastavro`) was needed at all. Don't assume
every module needs the same category of fix another module needed - check
first. The one real bug found (a Kafka consumer-group race in
`TrainingKafkaDataset.py`, fixed to match an already-working pattern
elsewhere in this exact repo) only surfaced via the actual end-to-end
test, not from reading the code. Full detail, the exact model-code
contract needed to construct a working test case, and what's explicitly
out of scope (AVRO input format - pre-existing, unreachable, multiple
independent bugs; confusion matrix generation; GPU path): `pytorch/CLAUDE.md`.
