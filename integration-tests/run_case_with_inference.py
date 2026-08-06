"""Ad hoc driver: runs one mnist_caseN_*.py module's real training, then
deploys the resulting trained model for real inference and sends one real
held-out MNIST test image through it - closing the gap between the
committed mnist_case*.py scripts (training-only) and mnist_inference_common.py
(inference helper, not wired into any of them). Not part of the committed
suite - a throwaway verification script for this session's post-wipe
regression pass.

Usage: uv run python3 run_case_with_inference.py <case_number>
"""

import importlib
import json
import sys
import uuid

from common import api_client
from mnist_inference_common import deploy_and_test_inference

DISTRIBUTED_CASES = {3, 4, 7, 8}


def main(case_number: int) -> None:
    module = importlib.import_module(f"mnist_case{case_number}_" + {
        1: "single_classic",
        2: "single_incremental",
        3: "distributed_classic",
        4: "distributed_incremental",
        5: "federated_single",
        6: "federated_incremental",
        7: "federated_distributed",
        8: "federated_distributed_incremental",
        9: "blockchain",
    }[case_number])

    training_summary = module.run()

    distributed = case_number in DISTRIBUTED_CASES
    if distributed:
        # Two TrainingResults (cloud + edge) - deploy the edge submodel for
        # inference, matching a real edge-deployment scenario. Match by
        # comparing each result's own model id against edge_model_id rather
        # than assuming list order.
        edge_model_id = training_summary["edge_model_id"]
        result_ids = [r["id"] for r in training_summary["results"]]
    else:
        result_ids = [training_summary["result_id"]]

    with api_client() as client:
        if distributed:
            target_result_id = None
            for rid in result_ids:
                full = client.get_result(rid)
                if full["model"]["id"] == edge_model_id:
                    target_result_id = rid
                    break
            assert target_result_id is not None, f"could not find edge result among {result_ids}"
        else:
            target_result_id = result_ids[0]

        run_id = uuid.uuid4().hex[:8]
        inference_summary = deploy_and_test_inference(
            client,
            target_result_id,
            run_id,
            case_label=f"case{case_number}",
            distributed=distributed,
        )

    print(json.dumps({"training": training_summary, "inference": inference_summary}, indent=2))


if __name__ == "__main__":
    main(int(sys.argv[1]))
