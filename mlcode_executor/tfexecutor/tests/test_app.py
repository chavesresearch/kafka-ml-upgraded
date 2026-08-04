"""Real endpoint tests for tfexecutor's Litestar app, against actual
TensorFlow model code (not mocked) - matches ../backend/CLAUDE.md's own
testing philosophy: real client, no live cluster/Kafka needed.

`/convert_to_tflite/` is tested for the "no quantization"/"dynamic
quantization" paths only - "int8" quantization needs a real Kafka broker
for its representative-dataset sampling (see CLAUDE.md's "still needed"
note) and is out of scope here.
"""

import io

import pytest
from litestar.testing import TestClient

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
