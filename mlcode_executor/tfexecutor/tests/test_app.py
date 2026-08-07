"""Real endpoint tests for tfexecutor's Litestar app, against actual
TensorFlow model code (not mocked) - matches ../backend/CLAUDE.md's own
testing philosophy: real client, no live cluster/Kafka needed.

`/convert_to_tflite/` is tested for the "no quantization"/"dynamic
quantization" paths only - "int8" quantization needs a real Kafka broker
for its representative-dataset sampling (see CLAUDE.md's "still needed"
note) and is out of scope here.
"""

import io
import time

import pytest
from litestar.testing import TestClient

import app as app_module
from app import app

VALID_MODEL_CODE = (
    "model = tf.keras.models.Sequential([\n"
    "    tf.keras.layers.Dense(4, activation='relu', input_shape=(2,)),\n"
    "    tf.keras.layers.Dense(1),\n"
    "])\n"
    "model.compile(loss='mse', optimizer='sgd')"
)


@pytest.fixture
def client():
    with TestClient(app=app) as c:
        yield c


def test_exec_tf_check_valid_model_returns_200(client):
    response = client.post(
        "/exec_tf/",
        json={
            "imports_code": "",
            "model_code": VALID_MODEL_CODE,
            "distributed": False,
            "request_type": "check",
        },
    )
    assert response.status_code == 200


def test_exec_tf_check_invalid_code_returns_400(client):
    response = client.post(
        "/exec_tf/",
        json={
            "imports_code": "",
            "model_code": "this is not valid python(((",
            "distributed": False,
            "request_type": "check",
        },
    )
    assert response.status_code == 400


def test_exec_tf_unknown_request_type_returns_404(client):
    response = client.post(
        "/exec_tf/",
        json={
            "imports_code": "",
            "model_code": VALID_MODEL_CODE,
            "distributed": False,
            "request_type": "not_a_real_type",
        },
    )
    assert response.status_code == 404


def test_exec_tf_load_model_returns_h5_bytes(client):
    response = client.post(
        "/exec_tf/",
        json={
            "imports_code": "",
            "model_code": VALID_MODEL_CODE,
            "distributed": False,
            "request_type": "load_model",
        },
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    assert len(response.content) > 0


def test_check_deploy_config_valid_kwargs_returns_200(client):
    response = client.post(
        "/check_deploy_config/",
        json={
            "batch": 4,
            "kwargs_fit": "{'epochs': 1}",
            "kwargs_val": "{}",
        },
    )
    assert response.status_code == 200


def test_check_deploy_config_missing_epochs_returns_400(client):
    response = client.post(
        "/check_deploy_config/",
        json={
            "batch": 4,
            "kwargs_fit": "{}",
            "kwargs_val": "{}",
        },
    )
    assert response.status_code == 400


def test_convert_to_tflite_no_quantization_returns_flatbuffer(client):
    import tensorflow as tf

    model = tf.keras.models.Sequential(
        [
            tf.keras.layers.Dense(4, activation="relu", input_shape=(2,)),
            tf.keras.layers.Dense(1),
        ]
    )
    model.compile(loss="mse", optimizer="sgd")
    model_path = "/tmp/tfexecutor_test_convert.h5"
    model.save(model_path)
    with open(model_path, "rb") as f:
        model_bytes = f.read()

    response = client.post(
        "/convert_to_tflite/",
        files={"42.h5": ("42.h5", io.BytesIO(model_bytes), "application/octet-stream")},
        data={"applyQuantization": "false"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    assert len(response.content) > 0


def test_convert_to_tflite_missing_file_returns_400(client):
    response = client.post(
        "/convert_to_tflite/",
        data={"applyQuantization": "false"},
    )
    assert response.status_code == 400


def test_exec_tf_hanging_code_is_killed_within_bounded_time(client, monkeypatch):
    """Covers the timeout/kill escalation ladder's actual slow-path -
    previously only the happy/error paths were tested, so a regression in
    the queue-read-before-join fix (see app.py's own comment on
    tensorflow_executor) would only ever have surfaced as a real cluster
    hang, not a test failure. EXEC_TIMEOUT_S is patched down from the
    production 60s so this doesn't make the suite itself slow - the
    subprocess spawn/kill machinery under test is identical either way,
    only the wait duration changes.
    """
    monkeypatch.setattr(app_module, "EXEC_TIMEOUT_S", 2)

    start = time.monotonic()
    response = client.post(
        "/exec_tf/",
        json={
            "imports_code": "",
            "model_code": "while True:\n    pass",
            "distributed": False,
            "request_type": "check",
        },
    )
    elapsed = time.monotonic() - start

    assert response.status_code == 400
    assert response.content == b""
    # Bounded, not "eventually" - the 2s timeout plus the two 5s
    # terminate/kill join windows in the escalation ladder is a real
    # upper bound; a regression back to the join-before-read deadlock
    # would hang here well past this, not just run slower.
    assert elapsed < 15
