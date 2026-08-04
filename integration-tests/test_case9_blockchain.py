"""CASE=9 (BlockchainSingleFederatedTraining, TensorFlow) - real API + real
Kafka + real federated-module round + a real local Ethereum devnet.

Same shape as CASE=5 (federated single), but `blockchain=True` -
`backend` dispatches to CASE=9 instead of 5
(`app/controllers/deployments.py`: `5 if not deployment.blockchain else 9`).
The main trainer deploys a real `FederatedLearning` smart contract to the
local Anvil devnet (`kustomize/local/resources/blockchain-devnet.yaml` -
see that file for why a local devnet instead of a real testnet) using the
precompiled artifact at `contracts/FederatedLearning.json`, then drives
the federated round's coordination through real contract calls
(saveTrainingSettings/saveGlobalModel/etc.), not just Kafka control
topics like CASE=5.

Requires `ENABLE_FEDML_BLOCKCHAIN=1` and the `fedml.blockchain.*` configmap
keys pointing at the local devnet (see kustomize/local/kustomization.yaml).
"""

import uuid

import numpy as np
from kafkaml_datasources import FederatedRawSink

from common import (
    BOOTSTRAP_SERVERS,
    TF_SINGLE_MODEL_CODE,
    api_client,
    create_configuration,
    create_deployment,
    create_model,
    wait_for_status,
)


def test_case9_blockchain_federated_training():
    run_id = uuid.uuid4().hex[:8]

    with api_client() as client:
        model_id = create_model(client, f"it-case9-model-{run_id}", TF_SINGLE_MODEL_CODE, framework="tf")
        config_id = create_configuration(client, f"it-case9-config-{run_id}", [model_id])
        deployment_id = create_deployment(
            client,
            configuration=config_id,
            batch=4,
            tf_kwargs_fit="epochs=1",
            tf_kwargs_val="",
            incremental=False,
            federated=True,
            blockchain=True,
            agg_rounds=1,
            min_data=10,
            agg_strategy="FedAvg",
            data_restriction={},
            conf_mat_settings=False,
        )

        topic = f"it-case9-data-{run_id}"
        sink = FederatedRawSink(
            boostrap_servers=BOOTSTRAP_SERVERS,
            topic=topic,
            deployment_id=deployment_id,
            description="integration-test-case9",
            validation_rate=0.2,
            test_rate=0.1,
        )
        rng = np.random.default_rng(9)
        for _ in range(40):
            x = rng.random(1).astype(np.float32)
            y = np.array([int(x[0] > 0.5)], dtype=np.uint8)
            sink.send(x, y)
        sink.close()

        results = wait_for_status(client, deployment_id, "finished", timeout_s=180)

        assert len(results) == 1
        result = results[0]
        assert result["train_metrics"], "expected non-empty train_metrics"
        print(f"CASE=9 OK - deployment {deployment_id}, result {result['id']}: {result['train_metrics']}")


if __name__ == "__main__":
    test_case9_blockchain_federated_training()
