---
sidebar_position: 4
---

# model_training

`model_training` is the set of container images that Kubernetes Jobs run
to actually train a model. `backend` downloads nothing and trains
nothing itself — it only creates the Job (see
`backend/app/job_manifest_generator.py`) with an image
(`tensorflow_model_training` or `pytorch_model_training`) and a `CASE` env
var, and the container does the rest: download the untrained model,
consume a Kafka data stream, train, and report metrics/results back to
`backend` over HTTP.

There are two independent implementations, `tensorflow/` and `pytorch/`,
which differ substantially in scope:

- **`tensorflow/`** implements all 9 training modes behind a `CASE`
  dispatch table.
- **`pytorch/`** implements exactly one training mode (single,
  non-distributed, non-incremental, non-federated classic training) —
  there is no `CASE` dispatch on the PyTorch side at all, just one
  `training.py` script.

## The CASE dispatch mechanism (TensorFlow)

`model_training/tensorflow/training.py` reads `CASE` (1-9) from the
environment and instantiates one of 9 training-mode classes, wrapped in
one of three orchestrator functions:

```python
case = int(os.environ.get('CASE'))
if case == NOT_DISTRIBUTED_NOT_INCREMENTAL:
  CloudBasedTraining(SingleClassicTraining())
elif case == NOT_DISTRIBUTED_INCREMENTAL:
  CloudBasedTraining(SingleIncrementalTraining())
elif case == DISTRIBUTED_NOT_INCREMENTAL:
  CloudBasedTraining(DistributedClassicTraining())
elif case == DISTRIBUTED_INCREMENTAL:
  CloudBasedTraining(DistributedIncrementalTraining())
elif case == FEDERATED_LEARNING:
  EdgeBasedTraining(SingleFederatedTraining())
elif case == FEDERATED_INCREMENTAL_LEARNING:
  EdgeBasedTraining(SingleFederatedIncrementalTraining())
elif case == FEDERATED_DISTRIBUTED_LEARNING:
  EdgeBasedTraining(DistributedFederatedTraining())
elif case == FEDERATED_DISTRIBUTED_INCREMENTAL_LEARNING:
  EdgeBasedTraining(DistributedFederatedIncrementalTraining())
elif case == BLOCKCHAIN_FEDERATED_LEARNING:
  from blockchainSingleFederatedTraining import BlockchainSingleFederatedTraining
  EdgeBlockchainBasedTraining(BlockchainSingleFederatedTraining())
```

The `CASE` integer constants themselves live in
`model_training/tensorflow/utils.py`:

| `CASE` | Constant | Class | Meaning |
|---|---|---|---|
| 1 | `NOT_DISTRIBUTED_NOT_INCREMENTAL` | `SingleClassicTraining` | Single model, bounded batch of Kafka data |
| 2 | `NOT_DISTRIBUTED_INCREMENTAL` | `SingleIncrementalTraining` | Single model, streaming/online Kafka data |
| 3 | `DISTRIBUTED_NOT_INCREMENTAL` | `DistributedClassicTraining` | Chain of submodels (father/child), bounded batch |
| 4 | `DISTRIBUTED_INCREMENTAL` | `DistributedIncrementalTraining` | Chain of submodels, streaming data |
| 5 | `FEDERATED_LEARNING` | `SingleFederatedTraining` | Single model, federated rounds across edge devices |
| 6 | `FEDERATED_INCREMENTAL_LEARNING` | `SingleFederatedIncrementalTraining` | Federated + streaming |
| 7 | `FEDERATED_DISTRIBUTED_LEARNING` | `DistributedFederatedTraining` | Federated + submodel chain |
| 8 | `FEDERATED_DISTRIBUTED_INCREMENTAL_LEARNING` | `DistributedFederatedIncrementalTraining` | Federated + submodel chain + streaming |
| 9 | `BLOCKCHAIN_FEDERATED_LEARNING` | `BlockchainSingleFederatedTraining` | Federated, coordinated/rewarded via an Ethereum smart contract |

So the mode is really the product of three independent axes —
**distributed** (single model vs. a father/child submodel chain),
**incremental** (bounded batch vs. indefinite Kafka stream), and
**federated** (trained entirely in this pod vs. coordinated across
external edge-device Jobs) — plus a 9th, blockchain-federated, variant
that adds on-chain coordination/reward on top of federated mode.

Each training class is thin: `singleClassicTraining.py`,
`distributedClassicTraining.py`, `singleIncrementalTraining.py`,
`distributedIncrementalTraining.py`, `singleFederatedTraining.py`,
`singleFederatedIncrementalTraining.py`, `distributedFederatedTraining.py`,
`distributedFederatedIncrementalTraining.py`, and
`blockchainSingleFederatedTraining.py` all subclass
`mainTraining.MainTraining` and implement the same interface
(`get_models`, `get_data`, `get_splits`, `train`, `saveMetrics`,
`sendMetrics`, and for CASE=1/3 also `test`/`getConfussionMatrix`) —
the actual logic lives in `MainTraining`; each subclass mostly just picks
which `MainTraining` method to call. This 1:1 class-per-mode structure is
intentionally not deduplicated (a "faithful port, not a redesign"
scoping decision) — expect real duplication between, e.g.,
`singleClassicTraining.py` and `distributedClassicTraining.py`.

### The three orchestrators

- **`CloudBasedTraining`** (`cloudBasedTraining.py`) — used for CASE 1-4.
  Subscribes to the Kafka control topic, waits for a control message whose
  key (a big-endian int) matches this pod's `deployment_id`, reads the
  data-source description out of the message body (Kafka topic, input
  format, split ratios, `total_msg`), builds the dataset, trains, and
  reports metrics — a single pass, no per-round loop.
- **`EdgeBasedTraining`** (`edgeBasedTraining.py`) — used for CASE 5-8.
  This pod acts as the **federated aggregator/coordinator**, not a
  trainer of raw data itself. See "Federated aggregation loop" below.
- **`EdgeBlockchainBasedTraining`** (`edgeBlockchainBasedTraining.py`) —
  used for CASE 9. Same shape as `EdgeBasedTraining` plus on-chain
  bookkeeping; see "Blockchain-federated training" below.

The `BlockchainSingleFederatedTraining` import is deliberately **lazy**
(imported inside the `elif case == BLOCKCHAIN_FEDERATED_LEARNING:` branch,
not at module level) so that the other 8 modes never pay the cost or risk
of importing the `web3`/`eth_abi` dependency chain — the same lazy-import
pattern `backend` uses for its own optional blockchain feature.

## Consuming Kafka training data

### TensorFlow

`decoders.py`'s `DecoderFactory.get_decoder(input_format, configuration)`
returns one of three decoders based on the `input_format` the control
message declares:

- **`RawDecoder`** — reads `data_type`/`label_type`/`data_reshape`/
  `label_reshape` from the configuration (via `string_to_numpy_type`) and
  decodes each Kafka message with `tf.io.decode_raw` + `tf.reshape`
  (`utils.py`'s `decode_input`/`decode_raw`).
- **`AvroDecoder`** — parses the Avro schema once via
  `fastavro.parse_schema`, then decodes each message with
  `fastavro.schemaless_reader` wrapped in `tf.py_function` (fastavro is
  not a native TF op, so it can't be traced directly inside the
  `.map()` call `mainTraining.py` builds).
- **`JsonDecoder`** / **`TelegrafStringJsonDecoder`** — plain
  `json.loads`, used for the online/streaming control-topic path.

The Kafka reads themselves go through `get_bounded_kafka_dataset` (bounded
offset-range replay, used by CASE 1/3/5/7) and `get_streaming_kafka_batches`
(polls a consumer group and yields one `tf.data.Dataset.from_tensor_slices`
mini-batch per poll cycle, used by CASE 2/4/6/8; `stream_timeout=-1`
means "poll forever", any positive value means "stop after that many ms
of silence"). `MainTraining.get_train_data`/`get_online_train_data`
(`mainTraining.py`) call these and then `.map(lambda x, y:
decoder.decode(x, y))` — decoding is always a separate step from the
Kafka read itself.

Both bounded and streaming readers use the `"topic:partition:start:end"`
control-message topic-string format and read data with
`consumer.assign([TopicPartition(...)])` + `.seek(...)`, **not**
`subscribe()` + `poll()` + `seek()`. This matters: a bounded, offset-range
read already knows its own start/end offsets up front, so it doesn't need
a consumer-group join/rebalance at all — `assign()` is synchronous and
skips the `FindCoordinator`/`JoinGroup`/`SyncGroup` round trip entirely.
Using `subscribe()`-style construction followed by a single `poll()` then
an immediate `seek()` is a latent race: a single `poll()` isn't guaranteed
to complete the rebalance before `seek()` runs, so the partition may not
be assigned to the consumer yet, raising `ValueError: Unassigned
partition`. `KafkaModelEngine.__createconsumer__` (used for federated
weight transfer, see below) follows the same `assign()`+`seek()` pattern.

### PyTorch

`TrainingKafkaDataset.py`'s `TrainingKafkaDataset` (a
`torch.utils.data.Dataset`) eagerly reads the entire bounded offset range
into `self.data` in `__init__` (no lazy/streaming path — PyTorch's
trainer has no incremental mode). It also uses `consumer.assign([tp])` +
`.seek(tp, start_offset)` in `__createconsumer__`, for the same reason.
`__decodedata__` supports a `RAW` branch (`np.frombuffer` +
`string_to_numpy_type`) but its `AVRO` branch is dead code: it calls
`self.avro_decoder(...)`, a method that doesn't exist (the real method is
the module-level `__avro_decoder__`, itself missing a `self` parameter),
and `DatumReader(data_scheme)` is constructed from a raw JSON string
instead of a parsed `avro.schema.Schema`. Any AVRO-format PyTorch training
job will hit this immediately — not something to route around silently if
extending this path.

`training.py`'s `get_train_data` wraps `TrainingKafkaDataset` with a
`torchvision.transforms.ToTensor()` transform whenever the declared
`data_reshape` has 2+ dimensions (image-shaped data), and
`torch.utils.data.random_split` does the train/validation/test split
using the same `validation_rate`/`test_rate` arithmetic as the TensorFlow
side.

## Reporting metrics and results back to `backend`

Both frameworks POST to `RESULT_URL` (`http://backend:8000/results/{id}`)
and `RESULT_URL.replace('results', 'results_metrics')` for per-epoch
metrics, retrying up to `RETRIES=10` times with a
`SLEEP_BETWEEN_REQUESTS=5`s pause on any non-200 response
(`mainTraining.py`'s `sendSingleMetrics`/`sendDistributedMetrics`/
`sendTempMetrics`, `training.py`'s `send_epoch_metrics` on the PyTorch
side). This 200-only check is a real wire contract, not an implementation
detail — `backend`'s `training_results.py` explicitly sets
`status_code=200` on `upload_result`/`upload_epoch_metrics` to match it;
Litestar's POST default is 201, which would otherwise make every
result/metrics POST look like a failure and retry forever.

The final-result POST is a multipart request with two file fields:

```python
files = {'trained_model': trained_model_file,
         'confussion_matrix': confussion_matrix_file}  # note the spelling
```

`confussion_matrix` (missing an "o") is the actual field name on the
wire — both training containers and `backend`'s
`POST /results/{id}` handler agree on this exact spelling; it is not a
typo to "fix" independently in one side only.

Distributed training (CASE 3/4) POSTs once per submodel instead
(`sendDistributedMetrics` iterates `self.tensorflow_models` and
`self.result_url`, which are lists), saving each submodel as its own
`trained_model_<n>.h5` and sending no confusion matrix.

## Federated aggregation loop

For CASE 5-8, `EdgeBasedTraining` (`edgeBasedTraining.py`) runs the
**aggregator** side of a federated round; the actual per-device training
happens in a separate satellite service,
`federated-module/federated_model_training` (Kubernetes Jobs created by
`federated_backend`), which is out of scope for this page.

Sequence, per `EdgeBasedTraining`:

1. `training.get_models()` downloads the pre-model.
2. `generate_and_send_data_standardization()` publishes the model's
   input/output shape to `MODEL_LOGGER_TOPIC` so
   `federated_model_control_logger` can register a `ModelSource` in
   `federated_backend`.
3. `generate_federated_kafka_topics()` creates three topics scoped to
   this federated run, all named `FED-{federated_string_id}-...`:
   `model_control_topic`, `model_data_topic`, and
   `agg_control_topic` (this trainer's own round-results inbox).
4. A `confluent_kafka.Consumer` subscribes to `agg_control_topic` with
   `group.id = 'group_id_' + federated_string_id`.
5. The main loop runs `while rounds < training.agg_rounds`: it sends the
   current model (`FederatedKafkaMLModelSink.send_model`, version `-1` on
   what it knows will be the last round) to the federated Kafka topics,
   then blocks polling `agg_control_topic` until an edge device's trained
   weights arrive, deserializes them with `KafkaModelEngine.setWeights`,
   calls `aggregate_model()`, and increments `rounds`.
6. When `rounds == agg_rounds`, the final model and metrics are sent to
   `backend` via `sendFinalMetrics` (the same 200-retry HTTP contract as
   the non-federated path).

`aggregate_model()`'s only implemented strategy is **`FedAvg`** — an
unweighted element-wise mean of the current model's weights and the
newly-received trained weights (`np.array(w).mean(axis=0)` over each
weight-tensor pair). `FedAvg+` (weighted-by-recency) and `Another` are
declared but raise `NotImplementedError`.

There is no lock-step/synchronized round barrier across edge devices —
`EdgeBasedTraining` simply waits for **one** control message per round
and aggregates it immediately; if multiple edge devices are training
against the same federated run, "a round" is really "the first result
that shows up on `agg_control_topic`", not a guaranteed quorum. This is
an architectural property of the loop shown above, not a bug — a
contributor adding multi-device-per-round support would need to change
this loop's blocking-poll-then-aggregate-one-message shape.

Model weights themselves travel over Kafka, not inline in the control
message: `KafkaModelEngine.__getModelWeights__` reads a
`"topic:partition:start:end"`-addressed range of weight messages (one
pickled numpy array per Kafka message,
`__decodedata__` unpickles `message.value` and reads the array's insert
position from `message.key`), the same assign+seek pattern described
above. `KafkaModelEngine.getModel`/`setWeights` then calls
`tf.keras.models.model_from_json` + `model.set_weights(...)` to
reconstruct the actual Keras model.

`FederatedKafkaMLModelSink.py`'s `__parse_model_compile_args` serializes
compile arguments via `model.get_compile_config()` (a Keras 3 API that
returns the optimizer/loss/metrics config pre-serialized in one call) —
this is read back by `KafkaModelEngine.__deserialize_compile_args__` on
the federated worker side (`federated-module/federated_model_training`),
which is untouched and still expects a generic passthrough dict, so the
two sides stay wire-compatible without any coordinated change.

## Blockchain-federated training (CASE 9)

`BlockchainSingleFederatedTraining` (`blockchainSingleFederatedTraining.py`)
subclasses `MainTraining` directly (not `SingleFederatedTraining`) and is
driven by `EdgeBlockchainBasedTraining` (`edgeBlockchainBasedTraining.py`),
which layers Ethereum smart-contract coordination on top of the same
federated round shape described above. It reads a block of
`ETH_*`-prefixed environment variables
(`load_blockchain_federated_environment_vars` in `utils.py`):
RPC URL, ERC20 token address/ABI, chain/network id, and a wallet
address/private key, plus the standard federated env vars
(`MODEL_LOGGER_TOPIC`, `FEDERATED_STRING_ID`, `AGGREGATION_ROUNDS`, etc.).
`blockchain_utils.py`'s `create_federated_learning_smart_contract` loads
a **precompiled** contract artifact (`contracts/FederatedLearning.json`)
rather than compiling Solidity at runtime — `web3` interacts with the
deployed `FederatedLearning` contract's ABI functions
(`saveTrainingSettings`, `saveGlobalModel`, its round queue, `setTokens`)
using the same `web3.py` client (`Web3(Web3.HTTPProvider(eth_rpc_url))`)
that talks to the Ethereum node, and issues a real ERC20 reward transfer
at the end of the round. `Web3`'s Python API is snake_case
(`to_checksum_address`, `build_transaction`, `sign_transaction`,
`send_raw_transaction`, `wait_for_transaction_receipt`, etc.) —
`TxReceipt.contractAddress` is the one field deliberately left
camelCase, since it's a pass-through of the raw Ethereum JSON-RPC
response field name rather than a `web3.py` API convention. Contract ABI
function names (`contract.functions.saveTrainingSettings(...)`) are
similarly unaffected by `web3.py`'s own naming, since they come from the
Solidity contract itself.

## TensorFlow vs. PyTorch: summary of differences

| | TensorFlow | PyTorch |
|---|---|---|
| `CASE` dispatch | 9 modes | none — always single/classic |
| Model download | `.h5` file, `keras.models.load_model()` | raw Python source, `exec()`'d directly (`utils.py`'s `download_model`) |
| Kafka reads | `tf.data.Dataset`-based (`get_bounded_kafka_dataset`/`get_streaming_kafka_batches`), Avro via `fastavro` + `tf.py_function` | eager `torch.utils.data.Dataset` (`TrainingKafkaDataset`), Avro branch present but unreachable (dead code, see above) |
| Training loop | `model.fit()` (Keras) | `ignite.engine.create_supervised_trainer`/`create_supervised_evaluator` |
| Metrics | `history.history` dict keys, `<submodel>_<metric>` convention for distributed | `ignite.metrics.*` attached to the trainer/evaluator via `model.metrics()` |
| Federated support | CASE 5-9 | none |
| Confusion matrix | `sklearn.metrics.confusion_matrix` + `seaborn`, gated by `CONF_MAT_CONFIG` | same libraries, same gate, generated inline in `training.py`'s `__main__` block instead of a `MainTraining` method |

The PyTorch model-code contract is worth calling out for anyone writing a
test model: `download_model()` `exec()`s the downloaded source directly
into `globals()`, so the submitted code must define a module-level
`model` variable — an `nn.Module` instance — with three additional
methods the platform calls back into: `optimizer()`, `loss_fn()`, and
`metrics()`. Because of the `exec()`-into-globals mechanism, names
imported at the top of `training.py`/`utils.py` (`Accuracy`, `Loss`,
`TensorboardLogger`, `torchvision.models`, etc.) are part of the
unqualified-reference surface a submitted model's methods can use even
though nothing in `training.py` itself calls them directly — they are not
dead imports safe to remove.

## Gotchas for contributors

- **Keras 3 reload requires re-binding the optimizer.** `utils.py`'s
  `load_model()` calls
  `model.compile_from_config(model.get_compile_config())` right after
  `keras.models.load_model()`. Without it, a model reloaded from disk
  keeps a *deserialized* optimizer object with a stale binding to its
  pre-save variable objects, and the first `.fit()` raises `ValueError:
  Unknown variable ... This optimizer can only be called for the
  variables it was originally built with`.
- **Distributed models need `y` replicated across outputs.** A model
  built by `create_distributed_model()` has one output per submodel in
  the chain, all supervised by the same label — Keras 3 requires
  `y_true`/`y_pred` to have matching structure, so anywhere a distributed
  model's dataset is fit/evaluated, the label must be mapped to an
  `N`-length tuple first: `.map(lambda x, y: (x, tuple(y for _ in
  range(self.N))))`. `create_distributed_model()`'s `metrics=` argument
  similarly must be a per-output dict (`{m.name: list(metrics) for m in
  self.tensorflow_models}`), not a flat list.
- **`consumer.assign()`, not `subscribe()`+`poll()`+`seek()`**, for every
  bounded/weight-transfer Kafka read in this module (see "Consuming Kafka
  training data" above) — this is the established, working pattern; don't
  reintroduce the subscribe-based race when adding a new bounded reader.
- **`SingleClassicTraining.test()`/`DistributedClassicTraining.test()`
  zip metric names against `evaluate()`'s return list by position**,
  and `evaluate()`'s actual return order (`[loss, accuracy, ...]`) doesn't
  match `epoch_training_metrics`'s dict key order (`[accuracy, loss,
  ...]`) — test-set metric values are very likely mislabeled. This is a
  pre-existing issue in both frameworks' original code, not something the
  modernization introduced; it has not been fixed (out of the "faithful
  port" scope), so don't assume `test_metrics` values are attributed to
  the right key without checking.
- **A federated-incremental round's `train_metrics` entry is that round's
  *final* epoch value only** — `parse_metrics`/`parse_distributed_metrics`
  in `mainTraining.py` append one value per aggregation round, and guard
  against a round finishing with an empty `validation` dict (a short
  streaming burst can complete without ever producing a held-out
  validation batch).

## See also

- [`backend`](./backend) — creates the training Job, serves the model
  file/architecture and result upload endpoints this module talks to.
- [`federated-module`](./federated-module) — the satellite service and
  edge-worker image (`federated_model_training`) that CASE 5-9 coordinate
  with.
- [`model_inference`](./model-inference) — deploys the finished
  `TrainingResult` for real-time prediction.
- [`datasources`](./datasources) — the client library used to publish
  training data into the Kafka topics this module consumes.
- [`mlcode-executor`](./mlcode-executor) — validates model code before a
  training Job is ever created.
