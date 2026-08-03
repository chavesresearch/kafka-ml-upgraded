"""PyTorch classic training - real API + real Kafka.

PyTorch's trainer has no `CASE` dispatch - a single, non-distributed,
non-incremental training mode (see model_training-upgraded/pytorch/CLAUDE.md).
"""

import uuid

import numpy as np
from kafkaml_datasources import RawSink

from common import (
    BOOTSTRAP_SERVERS,
    PTH_MODEL_CODE,
    api_client,
    create_configuration,
    create_deployment,
    create_model,
    wait_for_status,
)


def test_pytorch_classic_training():
    run_id = uuid.uuid4().hex[:8]

    with api_client() as client:
        model_id = create_model(client, f"it-pth-model-{run_id}", PTH_MODEL_CODE, framework="pth")
        config_id = create_configuration(client, f"it-pth-config-{run_id}", [model_id])
        deployment_id = create_deployment(
            client,
            configuration=config_id,
            batch=4,
            pth_kwargs_fit="max_epochs=1",
            pth_kwargs_val="",
            incremental=False,
            federated=False,
            conf_mat_settings=False,
        )

        topic = f"it-pth-data-{run_id}"
        sink = RawSink(
            boostrap_servers=BOOTSTRAP_SERVERS,
            topic=topic,
            deployment_id=deployment_id,
            description="integration-test-pytorch",
            validation_rate=0.2,
            test_rate=0.1,
        )
        rng = np.random.default_rng(5)
        for _ in range(40):
            x = rng.random(1).astype(np.float32)
            y = np.array([int(x[0] > 0.5)], dtype=np.uint8)
            sink.send(x, y)
        sink.close()

        results = wait_for_status(client, deployment_id, "finished")

        assert len(results) == 1
        result = results[0]
        assert result["train_metrics"], "expected non-empty train_metrics"
        print(f"PyTorch classic OK - deployment {deployment_id}, result {result['id']}: {result['train_metrics']}")


if __name__ == "__main__":
    test_pytorch_classic_training()
