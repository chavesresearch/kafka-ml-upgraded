"""Shared helpers for the real-MNIST, multi-epoch verification pass.

Unlike `common.py`'s tiny synthetic-data tests (designed to run in
seconds and prove the platform's plumbing works at all), these helpers
drive real MNIST digit images through real multi-epoch (`epochs=5`)
training, for all 9 `CASE`s, to confirm actual multi-epoch learning
happens end-to-end - not just that a single `.fit()` call succeeds.

MNIST itself is cached once at `.mnist-cache/mnist.npz` (gitignored,
~11MB) - downloaded from the same
`storage.googleapis.com/tensorflow/tf-keras-datasets/mnist.npz` URL
`tf.keras.datasets.mnist.load_data()` uses internally, so this doesn't
need `tensorflow` installed in this venv just to load a dataset.
"""

import re
import subprocess
from pathlib import Path

import numpy as np

MNIST_CACHE = Path(__file__).parent / ".mnist-cache" / "mnist.npz"
NAMESPACE = "kafkaml"


def load_mnist_train_subset(n: int, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Returns a real, shuffled, deterministic (per seed) subset of the
    real MNIST training set - genuine handwritten digit images, not
    synthetic data."""
    with np.load(MNIST_CACHE) as d:
        x_train, y_train = d["x_train"], d["y_train"]
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(x_train), size=n, replace=False)
    return x_train[idx], y_train[idx]


def load_mnist_test_sample(index: int = 0) -> tuple[np.ndarray, int]:
    """A real, held-out MNIST test-set image (never seen during any
    training run) + its true label, for inference verification."""
    with np.load(MNIST_CACHE) as d:
        x_test, y_test = d["x_test"], d["y_test"]
    return x_test[index], int(y_test[index])


# Single (non-distributed) model: raw 28x28 uint8 image in, 10-class
# softmax out. `Rescaling` normalizes pixels to [0, 1] inside the model
# graph itself (not in the data pipeline) so RawSink can keep sending
# plain uint8 bytes, matching examples/MNIST_RAW_format's own convention.
MNIST_SINGLE_MODEL_CODE = """model = tf.keras.Sequential([
    tf.keras.layers.Input((28, 28)),
    tf.keras.layers.Rescaling(1./255),
    tf.keras.layers.Flatten(),
    tf.keras.layers.Dense(128, activation="relu"),
    tf.keras.layers.Dense(10, activation="softmax")
])
model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])
"""

# Distributed father/child pair, scaled up from common.py's TF_CLOUD_MODEL_CODE/
# TF_EDGE_MODEL_CODE for real 28x28 images instead of a single scalar
# feature. Edge (child, leaf) takes the raw image; cloud (father, root)
# takes the edge's 32-dim intermediate feature vector. Distributed model
# code must end in a bare expression with no trailing newline - see
# mlcode_executor's format_ml_code, documented in
# model_training/tensorflow/CLAUDE.md.
MNIST_EDGE_MODEL_CODE = (
    'edge_input = tf.keras.Input(shape=(28, 28), name="edge_input")\n'
    'x = tf.keras.layers.Rescaling(1./255)(edge_input)\n'
    'x = tf.keras.layers.Flatten()(x)\n'
    'x = tf.keras.layers.Dense(64, activation="relu")(x)\n'
    'output_to_cloud = tf.keras.layers.Dense(32, activation="relu", name="output_to_cloud")(x)\n'
    'edge_output = tf.keras.layers.Dense(10, activation="softmax", name="edge_output")(x)\n'
    'tf.keras.Model(inputs=[edge_input], outputs=[output_to_cloud, edge_output], name="edge_model")'
)
MNIST_CLOUD_MODEL_CODE = (
    'cloud_input = tf.keras.Input(shape=(32,), name="cloud_input")\n'
    'x = tf.keras.layers.Dense(16, activation="relu")(cloud_input)\n'
    'cloud_output = tf.keras.layers.Dense(10, activation="softmax", name="cloud_output")(x)\n'
    'tf.keras.Model(inputs=cloud_input, outputs=cloud_output, name="cloud_model")'
)


def kubectl_pod_names(namespace: str = NAMESPACE) -> set[str]:
    out = subprocess.run(
        ["kubectl", "get", "pods", "-n", namespace, "-o", "name"],
        capture_output=True, text=True, check=True,
    )
    return set(out.stdout.split())


def kubectl_logs(pod_name: str, namespace: str = NAMESPACE) -> str:
    """`pod_name` may be a bare name or the `pod/xxx` form `kubectl get -o name` returns."""
    name = pod_name.split("/", 1)[-1]
    out = subprocess.run(
        ["kubectl", "logs", name, "-n", namespace, "--all-containers"],
        capture_output=True, text=True,
    )
    return out.stdout + out.stderr


def epoch_progress_lines(log_text: str) -> list[tuple[str, str]]:
    """Every real `Epoch N/M` line Keras's default fit() verbosity prints -
    the concrete evidence multi-epoch training actually ran for real,
    rather than inferring it indirectly from result metrics shape."""
    return re.findall(r"Epoch (\d+)/(\d+)", log_text)


def new_pods(before: set[str], namespace: str = NAMESPACE) -> list[str]:
    return sorted(kubectl_pod_names(namespace) - before)


def restart_federated_backend() -> None:
    """federated_backend never marks a matched Datasource/ModelSource row
    as consumed (documented, pre-existing gap - see
    model_training/tensorflow/CLAUDE.md's CASE 6-9 section) - restarting
    between federated case runs avoids stale registrations from an
    earlier case re-matching and spawning duplicate edge worker Jobs."""
    subprocess.run(
        ["kubectl", "rollout", "restart", "deployment/federated-backend", "-n", NAMESPACE],
        capture_output=True, text=True, check=True,
    )
    subprocess.run(
        ["kubectl", "rollout", "status", "deployment/federated-backend", "-n", NAMESPACE, "--timeout=60s"],
        capture_output=True, text=True, check=True,
    )
