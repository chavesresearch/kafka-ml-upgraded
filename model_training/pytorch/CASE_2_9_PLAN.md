# Plan: PyTorch CASE 2-9 support

**Status: not started.** `model_training/pytorch/` currently only implements
the CASE=1 equivalent (single, non-distributed, non-incremental, non-federated
classic training) - there is no `CASE` env var dispatch at all
(`training.py` always runs the same linear script). TensorFlow
(`model_training/tensorflow/`) implements all 9 CASEs. Nothing in the
frontend or backend gates a user from configuring a PyTorch deployment as
distributed/incremental/federated/blockchain today - `backend/app/
job_manifest_generator.py` and `frontend/src/views/DeploymentView.tsx` are
both 100% framework-agnostic, so a user can already build a Job manifest
that sets `CASE=6` (say) on the PyTorch training image. Today that Job
just silently runs plain CASE=1 training and ignores every federated env
var, rather than erroring - see FUTURE.md TODO/High item 4 for that
specific silent-failure bug, which this plan's CASE=5+ work directly
resolves once PyTorch actually reads `CASE`.

This document breaks the work into ordered phases so it can be picked up
incrementally, starting tomorrow, without needing to plan out every CASE
up front. Each phase lists the concrete new files/functions, what to port
directly vs. design from scratch, and a verification bar before moving on
- following this project's own standing practice (see `model_training/
tensorflow/CLAUDE.md`'s "CASE 1-9 - CONFIRMED PASSED" sections) of treating
"imports cleanly" and "actually trains end-to-end against a live cluster
with real data" as two different, both-required bars.

Source of truth for every TensorFlow reference below: `model_training/
tensorflow/{training,mainTraining,KafkaModelEngine,edgeBasedTraining,
edgeBlockchainBasedTraining,utils}.py`, `../../tf-kafka-dataset/src/
tf_kafka_dataset/datasets.py`, and `model_training/tensorflow/CLAUDE.md`.

## Phase 0 - dispatch skeleton (prerequisite for every other phase)

Cheap, mechanical, do this first regardless of which CASE comes next.

- `model_training/pytorch/config.py`: add the same 9 numeric `CASE`
  constants TF's `utils.py:30-38` defines
  (`NOT_DISTRIBUTED_NOT_INCREMENTAL = 1`, ... `BLOCKCHAIN_FEDERATED_LEARNING
  = 9`).
- `model_training/pytorch/utils.py`: port `load_distributed_environment_vars`/
  `load_incremental_environment_vars`/`load_federated_environment_vars`/
  `load_blockchain_federated_environment_vars` from TF's `utils.py:207-302`
  - pure `os.environ.get(...)` readers, no Keras dependency, copy the
  pattern directly. These env vars are **already being injected into the
  PyTorch container today** by the existing framework-agnostic
  `job_manifest_generator.py` whenever a PyTorch deployment is configured
  as distributed/incremental/federated/blockchain - this step only makes
  `pytorch/training.py` actually read them.
- `model_training/pytorch/training.py`: wrap the current CASE=1 script body
  in `if case == config.NOT_DISTRIBUTED_NOT_INCREMENTAL:` (reading `CASE`
  from env the same way TF's `training.py:30` does), with `elif` branches
  for each subsequent phase below as they land. Until a given CASE's
  branch exists, fall through to a clear `raise NotImplementedError(f"CASE
  {case} not yet supported for PyTorch")` - **this alone is a real,
  worthwhile fix**: it turns today's silent wrong-behavior (FUTURE.md
  TODO/High item 4) into a loud, correct failure for every CASE not yet
  ported, before any new CASE logic exists.

**Verification**: `uv run pytest -v` in `model_training/pytorch/` still
passes (no existing behavior changed for CASE=1); manually set
`CASE=5`/`CASE=9` env vars and confirm the new `NotImplementedError` fires
instead of silent classic training.

## Phase 1 - CASE 2 (single, incremental)

**Cost: moderate.** No PyTorch precedent exists for streaming/incremental
Kafka consumption today (`TrainingKafkaDataset` eagerly loads everything
bounded in `__init__`), but TF's `tf_kafka_dataset.get_streaming_kafka_batches`
(`datasets.py:70-127`) is a proven, already-verified blueprint built
directly against `kafka-python` - the same library PyTorch's own
`TrainingKafkaDataset.py` already uses, so this ports far more mechanically
than it sounds.

- New `model_training/pytorch/StreamingKafkaDataset.py` (name to taste):
  a plain Python generator/iterable, not a `torch.utils.data.Dataset`
  subclass (streaming has no fixed length) - `assign()`+`seek()` to the
  current end offset (avoiding TF's own historical subscribe+poll+seek
  race, see `pytorch/CLAUDE.md`'s existing writeup of that exact bug
  class already avoided in `TrainingKafkaDataset`), poll in a loop,
  yield a mini-batch whenever `stream_timeout` elapses with no new
  messages, matching `get_streaming_kafka_batches`'s poll/yield/reset-timer
  shape.
- `model_training/pytorch/training.py`: new incremental training loop
  (`elif case == config.NOT_DISTRIBUTED_INCREMENTAL:`) - consume streaming
  mini-batches, `DataLoader` per mini-batch, train, use Ignite's
  `@trainer.on(Events.EPOCH_COMPLETED)` (already used for CASE=1) to send
  per-mini-batch metrics. **Port the retry-on-exhausted-generator fix**
  from TF's `mainTraining.py`'s `train_incremental_model` (the
  `while 'model_trained' not in locals()` loop that re-fetches a fresh
  generator via `self.get_data(...)` on an empty pass) - this is a real,
  previously-shipped deadlock fix (see `federated-module/CLAUDE.md`'s
  "Real-MNIST multi-epoch pass" section for the original discovery), not
  optional polish; skipping it reintroduces a known bug class.
- Also port the "empty validation dict" `KeyError` fix from
  `mainTraining.py`'s `parse_metrics`/`saveSingleMetrics` (lines 174-177,
  200-203) into whatever PyTorch-side metrics-merge handles the
  incremental case's repeated partial results.

**Verification**: new `integration-tests/test_pytorch_case2_*.py`
(mirror `test_pytorch_classic.py`'s real-API-plus-real-Kafka-messages
shape, streaming a slow trickle of messages instead of one batch) reaching
a real `status: finished` result against a live cluster - not just an
import/unit-test pass. Add `model_training/pytorch/tests/` unit coverage
for the new streaming reader's pure helper methods (offset/timeout logic),
matching `test_training_kafka_dataset.py`'s existing
`__new__`-to-avoid-real-Kafka-I/O pattern.

## Phase 2 - CASE 3 / CASE 4 (distributed, +incremental)

**Cost: expensive, no in-repo PyTorch precedent.** This is the single
hardest design problem in the whole plan. TF's `create_distributed_model`
(`mainTraining.py:302-350`) builds one chained Keras functional model
wiring N submodels' outputs into the next submodel's inputs, with one
`compile()` call producing shared multi-output loss/metric bookkeeping -
there is no PyTorch analog anywhere in this codebase.

Needs a from-scratch design, not a port:

- How N independently-`exec()`'d `nn.Module` instances (each downloaded
  and exec()'d via the existing `download_model()`/model-code-contract
  pattern - see `pytorch/CLAUDE.md`'s "Model code contract" section)
  chain into one trainable graph. Candidate approach: a thin
  `nn.Module` wrapper whose `forward()` calls each submodel in sequence,
  feeding one's output as the next's input - closest structural analog
  to what the Keras functional composition achieves, but needs its own
  per-submodel loss terms (a `list[nn.Module]` of loss functions, one per
  submodel per TF's own per-submodel-loss config) and Ignite-compatible
  multi-output metrics (Ignite's `engine.state.metrics` doesn't have a
  built-in multi-output shape the way Keras's per-output-named history
  does - likely a `dict[submodel_index, dict[metric_name, value]]`
  convention, invented here, not borrowed).
- How each submodel's per-model metrics get reported back to its own
  distinct `result_id`/`result_url` - TF does this via submodel `.name`
  string-matching on flat Keras history keys; PyTorch will need an
  index-based scheme instead (submodels have no equivalent name
  namespace).
- Multi-model download (list of URLs, not one) - `utils.py`'s
  `download_model()` currently takes one URL; extend to a list, matching
  TF's `get_distributed_models`'s shape (`mainTraining.py:52-75`).
- Multi-URL/multi-file result POST (`sendDistributedMetrics` equivalent)
  - PyTorch's `training.py` already has a working single-model version
    of this POST logic (lines 367-401); generalize it to N models/URLs
    with `contextlib.ExitStack` for N open file handles, matching TF's
    own `sendDistributedMetrics` shape (`mainTraining.py:711-916`).

CASE 4 (distributed + incremental) is then largely additive once both
Phase 1 and this phase exist and compose correctly - TF's own
`CLAUDE.md` notes CASE 4 "just validates the CASE 2 and CASE 3 fixes
compose correctly," expect the same here.

**Verification**: same bar as Phase 1 - real end-to-end
`test_pytorch_case3_*.py`/`test_pytorch_case4_*.py` against a live
cluster with a real 2-submodel distributed deployment, not just an
import check. Given the design risk here, budget time for at least one
throwaway prototype script (`kubectl exec`-driven, matching this
project's own established debugging pattern) verifying the chained
`nn.Module` forward/backward pass actually produces sane gradients
before wiring it into the full training loop.

## Phase 3 - CASE 5-8 (federated, + distributed/incremental combos)

**Cost: expensive, and structurally the largest blocker in this whole
plan - not because of `model_training/pytorch` itself, but because
`federated-module/federated_model_training/pytorch/` doesn't exist at
all today** (confirmed: only a `.gitkeep`, per `federated-module/
CLAUDE.md`). This is a second, comparably-sized service to build, not a
file or two - it's the edge worker Job that trains locally on each
device and sends weights back; without it, no federated round can ever
complete for PyTorch regardless of what `model_training/pytorch` itself
can do.

Good news: most of the *transport* layer is already framework-agnostic
Kafka/pickle code with no Keras dependency, so this is more of a port
than a fresh design, unlike Phase 2:

- New `model_training/pytorch/KafkaModelEngine.py`: port TF's
  `KafkaModelEngine.py` - `__getModelWeights__`/
  `__splitPartitionsIntoControlMsgs__`/`__createconsumer__`/
  `__decodedata__` (lines 65-121) are pure `kafka-python` bounded-offset
  consumer + `pickle.loads`, already essentially identical in shape to
  `TrainingKafkaDataset`'s own consumer pattern - port near-verbatim.
  `getModel`/`setWeights` (11-26) swap `model_from_json`/`set_weights`/
  compile-arg deserialization for `model.load_state_dict(...)` - actually
  **simpler** than the TF side, since PyTorch's model source is already
  re-`exec()`'d fresh on every edge worker (no architecture-JSON
  round-trip needed), and optimizer/loss are already methods on the
  model instance per the existing `pytorch/CLAUDE.md` model-code
  contract, not something that needs re-serializing.
- New `model_training/pytorch/FederatedKafkaMLModelSink.py`: port TF's
  version - the partition/offset bookkeeping (`__get_partitions_and_offsets`,
  `__update_partitions`, `__send`) is 100% generic pickle+Kafka, no TF
  dependency at all; only `send_model` changes, sending
  `model.state_dict()` tensors (`.items()`) instead of
  `get_weights()`/`to_json()`/`get_compile_config()`.
- `aggregate_model`'s FedAvg (`edgeBasedTraining.py:18-43`): pure numpy
  arithmetic over zipped weight lists in TF - directly portable to
  PyTorch state_dict tensors (average per parameter key across the
  current global model and the received trained model).
- New `model_training/pytorch/edgeBasedTraining.py` (or fold into
  `training.py`'s CASE branches): port the aggregation-round loop shape
  from TF's `EdgeBasedTraining` - send current global weights, block on
  the first edge worker response, FedAvg-merge, repeat for
  `agg_rounds`, send final metrics. CASE 7/8 additionally need
  per-submodel weight transfer (N weight sets per round, not one) - only
  buildable after Phase 2's distributed-model design exists.
- **New service: `federated-module/federated_model_training/pytorch/`**
  - the edge worker. Structurally mirrors
  `federated-module/federated_model_training/tensorflow/` (same
  `Dockerfile` pattern including the non-root-user fix documented in
  `federated-module/CLAUDE.md`'s "CASE 6-9" section - a real,
  previously-hit blocker for the TF edge worker, don't reintroduce it
  here), consuming the per-round model via the new `KafkaModelEngine`,
  training locally via the existing single-model PyTorch training logic,
  sending results back via the new `FederatedKafkaMLModelSink`. This
  needs its own `pyproject.toml`/`uv.lock`, its own
  `.github/workflows/` entry (mirroring
  `federated_tensorflow_model_training.yml`), and its own `kustomize`
  wiring (new Job image referenced somewhere `federated_backend`'s
  `deploy_on_kubernetes` can pick up - check whether that function
  already branches on framework the way `backend`'s does, or needs a
  small addition).

**Verification**: same "real end-to-end, not just import-checked" bar,
but this phase specifically needs a full multi-service live-cluster run
(main trainer + both federated control-loggers + `federated_backend` +
the new PyTorch edge worker Job) to mean anything - a unit test alone
cannot prove a federated round actually completes. Follow
`federated-module/CLAUDE.md`'s own precedent: verify CASE 5 first (the
simplest federated combo) before attempting 6/7/8.

## Phase 4 - CASE 9 (blockchain federated, single/non-incremental only)

**Cost: expensive, but smaller than Phase 3 once Phase 3 (CASE 5) is
done** - the blockchain-interaction layer itself (`web3`/contract calls)
is framework-agnostic Python that doesn't care whether the coordinated
model is TF or PyTorch. Once CASE 5's PyTorch federated machinery exists,
this is "mostly" a matter of swapping the plain Kafka aggregation-control
loop for the contract-driven one - the same relative cost delta TF's own
CASE 5->9 already has.

- New `model_training/pytorch/blockchainSingleFederatedTraining.py` (or
  equivalent): port `write_control_message_into_blockchain`/
  `elements_to_aggregate`/`retrieve_last_model_from_queue`/
  `calculate_reward`/`reward_participants` from TF's
  `blockchainSingleFederatedTraining.py:249-402` - real `web3` contract
  calls (`FederatedLearning.sol` ABI), not framework-dependent.
  `load_blockchain_federated_environment_vars()` was already added in
  Phase 0.
- Match TF's own explicit scope limit: **no distributed or incremental
  blockchain combos** (TF's `edgeBlockchainBasedTraining.py:12-15,44-47,
  57-76` has `# TODO: Implement Incremental and Distributed Blockchain
  Federated Training if needed` - there is no CASE 10+ for those
  combos in this project at all, TF or PyTorch). Don't scope PyTorch
  CASE=9 wider than TF's own CASE=9.
- Same blockchain devnet verification approach TF used (see
  `model_training/tensorflow/CLAUDE.md`'s CASE 6-9 section): a local
  Anvil devnet, real contract deployment, real on-chain round
  coordination, real ERC20 reward transfer - not mocked.

**Verification**: real CASE=9 run against the same local Anvil devnet
already used for TF's CASE=9, reaching a real finished federated result
with actual on-chain transactions, not just a passing unit test.

## Suggested day-1 scope

Given the cost assessment above, **Phase 0 + Phase 1 (CASE 2) is a
realistic one-day target**: Phase 0 is a few dozen lines of mechanical
porting, and Phase 1 has a proven, already-verified TF blueprint to work
from even though it's genuinely new PyTorch code. Phases 2-4 each need
either real from-scratch design work (Phase 2's submodel chaining) or a
second service to stand up (Phase 3's edge worker) and should be scoped
as their own separate sessions rather than compressed into one day.

## Cross-references

- FUTURE.md TODO/High item 4 - the silent-wrong-behavior bug (PyTorch +
  federated deploys today) that Phase 0's `NotImplementedError` and
  Phase 3's real implementation both resolve, in that order.
- `model_training/tensorflow/CLAUDE.md` - the CASE 1-9 implementation
  this plan ports from, including its own "real bugs found" sections
  (Keras 3 y-replication, the incremental retry-on-exhausted-generator
  deadlock, the empty-validation-dict KeyError) - each has a PyTorch-side
  equivalent called out by phase above; don't skip them as "TF-specific,"
  most are generic to the streaming/federated design itself.
- `federated-module/CLAUDE.md` - the existing TF federated module's own
  bug history (mark-consumed race, `auto_offset_reset` replay bug,
  non-root Dockerfile fix) - Phase 3's new PyTorch edge worker service
  should be checked against each of these from the start, not
  rediscovered.
