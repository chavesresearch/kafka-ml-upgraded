---
sidebar_position: 3
---

# federated-module

`federated-module/` is the satellite service group that makes federated
learning ([Usage: Federated Learning](../usage/federated-learning))
possible. It is **not** a UI or monitoring side-concern — one of its
pieces, `federated_backend`, is the actual orchestrator that launches
edge-device training Jobs on Kubernetes. It's made of four independent
services:

| Service | Role |
|---|---|
| `federated_backend/` | Litestar API + matching engine + Kubernetes deploy — the orchestrator. |
| `federated_data_control_logger/` | Kafka-to-HTTP relay for datasource registrations. |
| `federated_model_control_logger/` | Kafka-to-HTTP relay for model registrations. |
| `federated_model_training/tensorflow/` | The edge-client container that actually trains locally on a device/partition (no PyTorch equivalent exists — federated CASE 5-8 are TensorFlow-only). |

## End-to-end flow

1. The main `model_training/tensorflow` trainer, running in a federated
   CASE (5-8), calls `generate_and_send_data_standardization()`, which
   publishes a model-registration message onto `MODEL_CONTROL_TOPIC`.
   Separately, `KafkaMLSink`-style datasource clients publish onto
   `DATA_CONTROL_TOPIC`.
2. `federated_model_control_logger` and `federated_data_control_logger` —
   two small Kafka-to-HTTP relay scripts, the same shape as the top-level
   `kafka_control_logger` — each consume their respective control topic
   and `POST` the payload to `federated_backend`'s
   `/model-control-logger/` or `/federated-datasources/` endpoint.
3. `federated_backend` persists each registration as a `ModelSource` or
   `Datasource` row, and on **every** new registration, checks it against
   *every* existing counterpart for a compatible match
   (`check_colission()` in `app/matching.py` — input shape, reshape,
   restrictions, and data volume must all line up). On a match, it calls
   the Kubernetes API directly (`app/kubernetes_deploy.py`'s
   `deploy_on_kubernetes()`) to launch a `federated_model_training` Job —
   there is no polling loop or separate scheduler process.
4. That Job is the edge client: it consumes the current round's model
   (architecture + weights) via `KafkaModelEngine`
   (`FED-{id}-model_control_topic`), trains locally on its own Kafka data
   partition, and sends results back via
   `FederatedKafkaMLAggregationSink` to
   `FED-{id}-agg_data_topic-{client}` / `FED-{id}-agg_control_topic`. The
   main trainer in `model_training/tensorflow` is the side that actually
   aggregates (FedAvg or similar) and drives the next round — see the
   [model_training page](./model-training).

`federated_model_training` itself never makes an HTTP call to anything —
it's purely Kafka-driven. Only the two logger scripts and
`federated_backend` speak HTTP, and only to each other.

## `federated_backend` internals

Rewritten from Django/DRF to Litestar to match the main `backend`'s stack,
with the same faithful-port goal: identical endpoint paths, request/response
shapes, and environment variable names, so the deployment manifest needed
no changes.

Layout: `app/{config,db,models,matching,kubernetes_deploy,controllers,main}.py`,
one file per concern (mirroring `backend/app/`'s own layout rather than a
Django `automl`/`autoweb` app split). `ModelSource`/`Datasource` are plain
SQLAlchemy 2.0 async models; their schema is created via
`Base.metadata.create_all()` at lifespan startup rather than real Alembic
migrations — proportionate for two small, stable tables.

A field-typing detail that matters for anyone touching `app/models.py`:
`ModelSource.blockchain` is a genuine native JSON column, because the real
wire format sends it as a nested dict. `data_restriction` /
`dataset_restrictions`, however, are plain `Text` columns, because the
real clients (`FederatedRawSink`'s default, and the main trainer's
`DATA_RESTRICTION` environment variable) always send those as
JSON-*encoded strings*, not native dicts — `check_colission()` itself
`json.loads()`s them before comparing. Getting this distinction backwards
previously caused a real (later reverted) bug: an ad-hoc test that POSTed
a raw Python dict for these fields crashed `json.loads()` on the receiving
end, which looked like an always-broken bug — but the crash was in the
test, not the code, since no real client ever sends a native dict for
those two fields.

`deploy_on_kubernetes` (`app/kubernetes_deploy.py`) is async, via
`kubernetes_asyncio`. It shares the exact `kubernetes_api_client()`
pattern used in `backend/app/utils.py`: building the `ApiClient` with
**no** explicit `Configuration` object, so it falls back to
`Configuration.get_default_copy()` internally and correctly picks up
`load_incluster_config()`'s in-cluster defaults — see the
[backend page](./backend#kubernetes-access) for the full explanation of
why a directly-constructed `Configuration()` silently targets
`http://localhost` instead.

### Consumed-registration bookkeeping

Two correctness properties matter for how `federated_backend` and its two
logger relays behave under restarts, and both are load-bearing for
avoiding duplicate Jobs:

1. `create_datasource`/`model_from_control_logger` delete both matched
   rows (`await db_session.delete(...)`) immediately after
   `deploy_on_kubernetes` succeeds. Without this, every new registration
   re-scans and can re-match against every row ever inserted, so leaving
   even one federated CASE running across several restarts of this
   service could spin up duplicate edge-worker Jobs from stale earlier
   registrations.
2. `federated_model_control_logger`'s Kafka consumer must **not** pass
   `auto_offset_reset='earliest'`. Combined with a fresh random
   `group_id` on every restart (so there's never a prior committed offset
   to resume from), that setting made every restart replay the control
   topic's *entire* retained history from the beginning, re-POSTing every
   registration ever published in the session — its sibling
   `federated_data_control_logger` never passed this kwarg and correctly
   defaults to `'latest'`.

Both fixes are needed together: mark-as-consumed alone doesn't help if a
logger restart recreates fresh unconsumed rows from replayed history, and
the offset fix alone doesn't stop within-one-session re-matching of rows
that were never deleted.

## `federated_model_training/tensorflow/` internals

Structured the same way as `model_training/tensorflow` and reuses several
of its modules directly rather than re-implementing them:

- `kafka_dataset.py` and `decoders.py` are copied verbatim from
  `model_training/tensorflow/` — identical topic-spec wire format and
  `AvroDecoder` shape, so no adaptation was needed.
- `KafkaModelEngine.py` / `FederatedKafkaMLAggregationSink.py` use
  `consumer.assign(...)` directly (not subscribe+poll+seek) and transfer
  models via `model.to_json()` / `model_from_json()` +
  `get_weights()`/`set_weights()`.
- `federated_mainTraining.py` dispatches on the same `CASE` numbering
  concept as the main trainer, with classic/incremental and
  single/distributed/blockchain variants (`train_classic_model`,
  `train_incremental_model`, and semi-supervised counterparts).
- `federated_blockchainSingleClassicTraining.py` handles the on-chain
  variant, calling into the same deployed `FederatedLearning.sol`
  contract the cloud side coordinates through.

## Independence from the main `backend`

`federated_backend` deliberately does not import anything from
`backend/`, even though both are Litestar services with a nearly
identical `kubernetes_api_client()` helper — the two services are meant
to be deployable and scalable independently, and the duplication is
judged cheaper than a shared internal package for two small helper
functions.

## See also

- [model_training](./model-training) — runs the main trainer side of
  every federated CASE, including the FedAvg aggregation loop that
  drives rounds.
- [backend](./backend) — the main API; shares the
  `kubernetes_api_client()` in-cluster-configuration pattern with
  `federated_backend`.
- [kustomize](./kustomize) — `federated-module/kustomize/` holds this
  module's own overlays, deployed alongside the main `kustomize/` tree.
