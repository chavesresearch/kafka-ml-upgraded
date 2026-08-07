---
sidebar_position: 6
---

# Blockchain-Traced Training

Blockchain-traced training coordinates a [federated learning](./federated-learning)
round through a smart contract instead of (or alongside) plain Kafka
control topics, so the aggregation round and each device's contribution
are recorded on-chain — and each participating device is paid a real
ERC-20 token reward proportional to its contribution once a round
finishes.

This is the [Interactive Showcase](/showcase)'s CASE 9. The showcase's
animation is illustrative only (simulated timing/metrics, says so
on-screen) — this page is the operational how-to for actually running
it.

Currently only TensorFlow supports blockchain-traced training, and only
the single (non-distributed, non-incremental) federated combination —
the same scope limit the platform's own CASE dispatch has. Everything in
[Federated Learning](./federated-learning) still applies; this page only
covers what's different.

## What you need

1. **An Ethereum-compatible chain reachable from the cluster** — a real
   network, a hosted testnet, or a local devnet. For local development,
   `kustomize/local` already wires up
   [Anvil](https://book.getfoundry.sh/anvil/) (Foundry's dev chain) as
   an in-cluster `blockchain` Deployment — deterministic pre-funded
   accounts, instant blocks, zero external network dependency. See
   `kustomize/local/resources/blockchain-devnet.yaml`.
2. **A funded wallet** the backend will sign transactions with (deploying
   the reward-token contract, writing round-coordination messages,
   paying out rewards). For the local Anvil devnet, this is simply
   Anvil's own well-known default account #0 — not a real secret, since
   everyone running the devnet locally gets the identical funded account
   by design.
3. **The `kafkaml-blockchain-credentials` Secret**, holding that wallet's
   private key. This is deliberately never a ConfigMap value like the
   rest of the blockchain settings below — a private key is not
   plaintext-safe config. Create it out-of-band:

   ```sh
   kubectl create secret generic kafkaml-blockchain-credentials \
     -n kafkaml --from-literal=wallet-key=<your private key>
   ```

   `kustomize/local` already provides this Secret pre-filled with
   Anvil's own public dev key, safe to commit for that reason (see
   `kustomize/local/resources/blockchain-wallet-secret.yaml`) — **never**
   put a real wallet key directly in a kustomize resource the way that
   file does for the local devnet.

## Enabling it

Set these in `kustomize/base/resources/kafkaml-configmap.yaml` (or an
overlay's `configMapGenerator`, the pattern `kustomize/local` already
uses):

| Key | Purpose | `kustomize/local`'s value |
|---|---|---|
| `fedml.blockchain.enable` | Master switch — `"0"` by default. | `"1"` |
| `fedml.blockchain.rpc-url` | The chain's JSON-RPC endpoint. | `http://blockchain:8545` (the in-cluster Anvil Service) |
| `fedml.blockchain.chain-id` / `fedml.blockchain.network-id` | Must match the target chain. Anvil's default chain id is `31337`. | `31337` / `31337` |
| `fedml.blockchain.wallet-address` | The public address matching the Secret's private key. | Anvil's account #0 address |
| `fedml.blockchain.blockscout-url` | Optional block explorer link shown in the UI. | unset locally (no explorer for the devnet) |
| `fedml.blockchain.token-name` / `fedml.blockchain.token-symbol` | The ERC-20 reward token's name/symbol, deployed fresh on backend startup. | `KafkaML-FedToken` / `KFKMLA` |

`ENABLE_FEDML_BLOCKCHAIN=1` also matters at training-container level —
it's what gates the `web3`/contract-interaction imports in
`model_training/tensorflow` from even being attempted (see that module's
own docs for why this is a lazy import, not a top-level one).

Apply both together for local development:

```sh
kubectl apply -k kustomize/local
```

## Using it

Once enabled, a **"Blockchain-traced training"** checkbox appears on the
deployment form alongside the federated-learning fields (visible only
when federated learning is already checked). Check it, deploy like any
other federated configuration, then send training data the same way you
would for [Federated Learning](./federated-learning) — the extra
on-chain coordination and reward payout happen automatically per round,
with no extra client-side steps.

If you used the MNIST model, run:

```sh
python examples/FEDERATED_MNIST_RAW_format/mnist_dataset_federated_training_example.py
```

## What actually happens on-chain, briefly

`backend` deploys a reward-token contract (`Token.sol`, an ERC-20
constructed with your configured name/symbol) and a coordination
contract (`FederatedLearning.sol`) once, on startup, using the
credentials above. Each training round, the current global model's
round-coordination message is written on-chain instead of (only) a plain
Kafka control topic; devices read it, train locally, and their
completion is likewise recorded on-chain. Once a round's contributions
are aggregated, each participating device receives a real ERC-20
transfer sized by its contribution. See `backend/app/blockchain.py` and
the [model_training module page](../modules/model-training) for the
implementation details, contract sources, and how this was verified end
to end against the local Anvil devnet.
