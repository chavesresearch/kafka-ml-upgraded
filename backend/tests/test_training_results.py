"""TrainingResult upload-to-finished flow - mirrors the old Django
`ResultViewTest.test_upload_results` theme, but against this port's real,
current contract: `train_metrics`/`val_metrics`/`test_metrics` are JSON
dicts (matching what `model_training/*`'s trainers actually POST - see
`app/schemas/__init__.py`'s `training_result_dict`), not the old test's
flat `train_loss`/`val_loss` scalar strings, which don't exist on this
model at all (see `app/models.py`'s `TrainingResult`).

A `Deployment`/`TrainingResult` row is seeded directly via
`async_session_maker()`, bypassing the Kubernetes-dependent
`POST /deployments/` flow entirely - the same pattern `CLAUDE.md`
recommends and the one used throughout this project's own real
end-to-end testing (see `model_training/tensorflow/CLAUDE.md`).

Seeding runs via a plain `asyncio.run(...)` in an otherwise-synchronous
test function, rather than an `async def` test - Litestar's `TestClient`
manages its own event loop internally for each `client.get/post(...)`
call, and nesting that inside a loop pytest-asyncio is already driving
(which an `async def` test would require) risks a "loop already running"
conflict. Sequential separate `asyncio.run()` calls (seed, then plain
sync HTTP calls) sidesteps that entirely.
"""

import asyncio
import json

from app.db import async_session_maker
from app.models import Configuration, Deployment, MLModel, TrainingResult

CODE = 'model = "not real code"'


async def _seed_training_result_async(name_prefix: str) -> int:
    async with async_session_maker() as session:
        async with session.begin():
            model = MLModel(name=f"{name_prefix}-model", code=CODE, framework="tf")
            config = Configuration(name=f"{name_prefix}-cfg", ml_models=[model])
            deployment = Deployment(configuration=config, batch=4)
            result = TrainingResult(deployment=deployment, model=model)
            session.add(result)
            await session.flush()
            return result.id


def _seed_training_result(name_prefix: str) -> int:
    return asyncio.run(_seed_training_result_async(name_prefix))


def test_upload_result_marks_finished_with_real_metrics(client):
    result_id = _seed_training_result("res-upload")

    metrics = {
        "train_metrics": {"accuracy": [0.5, 0.6], "loss": [0.8, 0.7]},
        "val_metrics": {"accuracy": [0.55], "loss": [0.75]},
        "training_time": 12.5,
    }
    resp = client.post(
        f"/results/{result_id}",
        data={"data": json.dumps(metrics)},
        files={"trained_model": ("model.h5", b"fake h5 bytes", "application/octet-stream")},
    )
    assert resp.status_code == 200

    result = next(r for r in client.get("/results/").json() if r["id"] == result_id)
    assert result["status"] == "finished"
    assert result["train_metrics"] == metrics["train_metrics"]
    assert result["val_metrics"] == metrics["val_metrics"]
    assert result["training_time"] == metrics["training_time"]


def test_upload_result_not_found(client):
    resp = client.post(
        "/results/999999",
        data={"data": json.dumps({"train_metrics": {}})},
        files={"trained_model": ("model.h5", b"x", "application/octet-stream")},
    )
    assert resp.status_code == 400


def test_upload_epoch_metrics_mid_training(client):
    """POST /results_metrics/{id} - the per-epoch progress updates a
    training container sends while still running (before the final
    POST /results/{id})."""
    result_id = _seed_training_result("res-epoch")

    resp = client.post(
        f"/results_metrics/{result_id}",
        data={"data": json.dumps({"train_metrics": {"loss": [0.9]}, "val_metrics": {"loss": [0.95]}})},
    )
    assert resp.status_code == 200

    result = next(r for r in client.get("/results/").json() if r["id"] == result_id)
    # Not finished yet - only the final POST /results/{id} sets that.
    assert result["status"] == "created"
    assert result["train_metrics"] == {"loss": [0.9]}


def test_deploy_inference_requires_finished_result(client):
    """`POST /results/inference/{id}` should refuse a result that hasn't
    finished training yet - confirms this without needing a real
    Kubernetes cluster (the handler checks `result.status` before ever
    touching the Kubernetes client)."""
    result_id = _seed_training_result("res-infer-notfinished")

    resp = client.post(
        f"/results/inference/{result_id}",
        json={"input_topic": "in", "output_topic": "out"},
    )
    assert resp.status_code == 400
