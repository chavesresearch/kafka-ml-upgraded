"""Real endpoint tests for pthexecutor's Litestar app, against actual
PyTorch model code (not mocked) - same philosophy as
../../tfexecutor/tests/test_app.py and ../../../backend/CLAUDE.md.

A valid Kafka-ML PyTorch model must define `loss_fn()`, `optimizer()`, and
`metrics()` methods on top of the usual `nn.Module` - see app.py's
`get_sample_model()` for the reference shape this mirrors.
"""

import time

import pytest
from litestar.testing import TestClient

import app as app_module
from app import app

VALID_MODEL_CODE = (
    "class SampleNet(nn.Module):\n"
    "    def __init__(self):\n"
    "        super().__init__()\n"
    "        self.layer = nn.Sequential(nn.Linear(2, 4), nn.Linear(4, 1))\n"
    "\n"
    "    def forward(self, x):\n"
    "        return self.layer(x)\n"
    "\n"
    "    def loss_fn(self):\n"
    "        return nn.MSELoss()\n"
    "\n"
    "    def optimizer(self):\n"
    "        return torch.optim.SGD(self.parameters(), lr=0.01)\n"
    "\n"
    "    def metrics(self):\n"
    "        return {'loss': Loss(self.loss_fn())}\n"
    "\n"
    "model = SampleNet()"
)


@pytest.fixture
def client():
    with TestClient(app=app) as c:
        yield c


def test_exec_pth_check_valid_model_returns_200(client):
    response = client.post(
        "/exec_pth/",
        json={
            "imports_code": "",
            "model_code": VALID_MODEL_CODE,
            "distributed": False,
            "request_type": "check",
        },
    )
    assert response.status_code == 200


def test_exec_pth_check_invalid_code_returns_400(client):
    response = client.post(
        "/exec_pth/",
        json={
            "imports_code": "",
            "model_code": "this is not valid python(((",
            "distributed": False,
            "request_type": "check",
        },
    )
    assert response.status_code == 400


def test_exec_pth_strips_pretrained_true(client):
    """`pretrained=True` is stripped before exec (app.py:53) so a pasted
    torchvision snippet doesn't try to download real pretrained weights
    during a model-definition check."""
    response = client.post(
        "/exec_pth/",
        json={
            "imports_code": "",
            "model_code": VALID_MODEL_CODE.replace(
                "self.layer = nn.Sequential(nn.Linear(2, 4), nn.Linear(4, 1))",
                "self.layer = nn.Sequential(nn.Linear(2, 4), nn.Linear(4, 1))  # pretrained=True",
            ),
            "distributed": False,
            "request_type": "check",
        },
    )
    assert response.status_code == 200


def test_exec_pth_unknown_request_type_returns_404(client):
    response = client.post(
        "/exec_pth/",
        json={
            "imports_code": "",
            "model_code": VALID_MODEL_CODE,
            "distributed": False,
            "request_type": "not_a_real_type",
        },
    )
    assert response.status_code == 404


def test_exec_pth_input_shape_returns_text(client):
    response = client.post(
        "/exec_pth/",
        json={
            "imports_code": "",
            "model_code": VALID_MODEL_CODE,
            "distributed": False,
            "request_type": "input_shape",
        },
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")


def test_check_deploy_config_valid_kwargs_returns_200(client):
    response = client.post(
        "/check_deploy_config/",
        json={
            "batch": 4,
            "kwargs_fit": "{'max_epochs': 1}",
            "kwargs_val": "{}",
        },
    )
    assert response.status_code == 200


def test_check_deploy_config_missing_max_epochs_returns_400(client):
    response = client.post(
        "/check_deploy_config/",
        json={
            "batch": 4,
            "kwargs_fit": "{}",
            "kwargs_val": "{}",
        },
    )
    assert response.status_code == 400


def test_exec_pth_hanging_code_is_killed_within_bounded_time(client, monkeypatch):
    """Same coverage gap/fix as tfexecutor/tests/test_app.py's identical
    test - see that file's comment for the full rationale. EXEC_TIMEOUT_S
    patched down from the production 60s so this doesn't slow the suite;
    the subprocess spawn/kill machinery under test is unchanged.
    """
    monkeypatch.setattr(app_module, "EXEC_TIMEOUT_S", 2)

    start = time.monotonic()
    response = client.post(
        "/exec_pth/",
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
    assert elapsed < 15
