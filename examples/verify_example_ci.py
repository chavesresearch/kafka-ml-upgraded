"""Real end-to-end CI verification for one examples/ tutorial.

Creates a real model/configuration/deployment via `kafkaml-client`
(against a real, already-deployed backend), runs the example's own
producer script against it - unmodified, aside from that script's
existing `KAFKAML_DEPLOYMENT_ID` env-var override (defaults to `1`,
overridden here to whatever deployment was actually created, so this
doesn't collide with any other data already on the same cluster) - and
waits for a real "finished" training result.

This is distinct from (and a superset of) `check_imports.py`'s job in
`.github/workflows/examples.yml`'s existing GitHub-hosted job: that one
proves an example's dependencies still resolve, never actually running
the scripts (no live Kafka broker on a hosted runner). This script
proves the example's *documented model code* and *producer script*
still genuinely work end to end - the class of bug `check_imports.py`
structurally cannot catch (both real bugs found in this project's
`examples/` on 2026-08-07 - a Keras-3-incompatible model layer, and a
Kafka consumer race - were import-clean and only surfaced by actually
running the scripts against a live cluster).

Needs a real local Kubernetes cluster with backend/kafka reachable at
localhost:8000/localhost:9094 (same prerequisites as
`integration-tests/`) - meant to be dispatched from
`.github/workflows/examples.yml`'s `real-execution` job on a self-hosted
runner, not runnable on a GitHub-hosted one.

Usage: python verify_example_ci.py <example-name>
"""

import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "kafkaml-client", "src"))

from kafkaml_client import KafkaMLClient  # noqa: E402

# Model code matching each example's README exactly (kept in sync by
# hand - see that README if this ever needs updating). Only examples
# with a small, locally-available dataset are covered here; MNIST's own
# full 60k-image example is deliberately not included - it's a multi-
# minute send on every run for no extra verification value over what a
# manual spot-check already covers periodically, and would make this job
# too slow to run routinely.
EXAMPLES = {
    "hcopd": {
        "dir": "HCOPD_Avro_format",
        "framework": "tf",
        "model_code": (
            "model = tf.keras.Sequential([\n"
            "    tf.keras.layers.Input(shape=(3,)),\n"
            "    tf.keras.layers.Dropout(0.2),\n"
            "    tf.keras.layers.Dense(4, activation='sigmoid'),\n"
            "    tf.keras.layers.Dense(2, activation='softmax')\n"
            "])\n"
            "model.compile(keras.optimizers.Adam(learning_rate=.0001), "
            "loss='sparse_categorical_crossentropy', metrics=['accuracy'])"
        ),
        "producer_script": "HCOPD_data_stream_producer.py",
        "tf_kwargs_fit": "epochs=2",
    },
}


def main(name: str) -> None:
    if name not in EXAMPLES:
        sys.exit(f"Unknown example {name!r} - choices: {', '.join(EXAMPLES)}")
    example = EXAMPLES[name]
    base_url = os.environ.get("KAFKAML_BACKEND_URL", "http://localhost:8000")

    with KafkaMLClient(base_url) as client:
        model_id = client.create_model(
            f"ci-{name}-model", example["model_code"], framework=example["framework"]
        )
        config_id = client.create_configuration(f"ci-{name}-config", [model_id])
        deployment_id = client.create_deployment(
            configuration=config_id, batch=4, tf_kwargs_fit=example["tf_kwargs_fit"]
        )
        print(f"Created deployment {deployment_id} for {name!r}, running {example['producer_script']}...")

        example_dir = os.path.join(os.path.dirname(__file__), example["dir"])
        subprocess.run(
            [sys.executable, example["producer_script"]],
            cwd=example_dir,
            env={**os.environ, "KAFKAML_DEPLOYMENT_ID": str(deployment_id)},
            check=True,
        )

        results = client.wait_for_results(deployment_id, timeout=180)
        print(f"OK: {name!r} training finished - {results[0]['train_metrics']}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(f"Usage: python {sys.argv[0]} <example-name>")
    main(sys.argv[1])
