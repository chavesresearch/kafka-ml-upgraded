"""create_deployment must clean up any Kubernetes Job it already created
for an earlier root model when a later model's Job creation fails -
otherwise the request's DB transaction rolls back (Deployment/
TrainingResult rows disappear) while the earlier Job keeps running for
real, posting results against an id that no longer exists. See
FUTURE.md/CLAUDE.md for the full bug writeup.

Mocks kubernetes_api_client/load_incluster_config/BatchV1Api - the one
genuinely external dependency this test would otherwise need a live
cluster for, same reasoning as test_inferences.py.
"""

from unittest.mock import AsyncMock, MagicMock, patch

CODE = 'model = "not real code, _check_model_code is mocked"'


def _create_model(client, name: str) -> int:
    with patch("app.controllers.models._check_model_code", new=AsyncMock(return_value=True)):
        client.post("/models/", json={"name": name, "code": CODE, "framework": "tf"})
    return next(m["id"] for m in client.get("/models/").json() if m["name"] == name)


def _fake_k8s_client():
    """A context-manager-compatible fake standing in for
    kubernetes_api_client(...)'s return value."""
    fake_client = MagicMock()
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)
    return fake_client


def test_partial_job_failure_cleans_up_the_earlier_already_created_job(client):
    model_a = _create_model(client, "deploy-cleanup-model-a")
    model_b = _create_model(client, "deploy-cleanup-model-b")

    client.post(
        "/configurations/",
        json={"name": "deploy-cleanup-cfg", "ml_models": [model_a, model_b]},
    )
    config_id = next(
        c["id"] for c in client.get("/configurations/").json() if c["name"] == "deploy-cleanup-cfg"
    )

    batch_api = MagicMock()
    # First model's Job creation succeeds; the second's fails - exactly
    # the partial-failure scenario this fix handles.
    create_response = MagicMock(status="created")
    batch_api.create_namespaced_job = AsyncMock(
        side_effect=[create_response, RuntimeError("cluster briefly unreachable")]
    )
    batch_api.delete_namespaced_job = AsyncMock()

    with (
        patch("app.controllers.deployments.k8s_config.load_incluster_config"),
        patch("app.controllers.deployments.kubernetes_api_client", return_value=_fake_k8s_client()),
        patch("app.controllers.deployments.k8s_client.BatchV1Api", return_value=batch_api),
    ):
        response = client.post("/deployments/", json={"configuration": config_id, "batch": 4})

    assert response.status_code == 400

    # The already-created first Job must have been cleaned up, not left
    # orphaned - this is the actual fix.
    assert batch_api.delete_namespaced_job.await_count == 1
    deleted_name = batch_api.delete_namespaced_job.await_args.kwargs["name"]
    created_name = batch_api.create_namespaced_job.await_args_list[0].kwargs["body"]["metadata"]["name"]
    assert deleted_name == created_name

    # And the DB transaction rolled back as before - no Deployment row
    # survives a failed create_deployment call.
    deployments = client.get(f"/deployments/{config_id}").json()
    assert deployments == []


def test_federated_deployment_with_pytorch_model_is_rejected(client):
    """PyTorch has no CASE dispatch and no federated_model_training/pytorch
    edge worker at all - without this check, a federated deployment
    including a PyTorch model would silently run plain classic training
    while backend records the deployment as federated (FUTURE.md High
    item 4). No Kubernetes mocking needed - this must reject before ever
    reaching the Job-creation loop."""
    with patch("app.controllers.models._check_model_code", new=AsyncMock(return_value=True)):
        client.post(
            "/models/",
            json={"name": "deploy-pth-federated-model-pth", "code": CODE, "framework": "pth"},
        )
    pth_model_id = next(
        m["id"] for m in client.get("/models/").json() if m["name"] == "deploy-pth-federated-model-pth"
    )

    client.post(
        "/configurations/",
        json={"name": "deploy-pth-federated-cfg", "ml_models": [pth_model_id]},
    )
    config_id = next(
        c["id"] for c in client.get("/configurations/").json() if c["name"] == "deploy-pth-federated-cfg"
    )

    response = client.post(
        "/deployments/",
        json={
            "configuration": config_id,
            "batch": 4,
            "federated": True,
            "agg_rounds": 1,
            "min_data": 1,
            "data_restriction": "{}",
            "agg_strategy": "FedAvg",
        },
    )

    assert response.status_code == 400
    assert "TensorFlow" in response.json()["detail"]
    assert client.get(f"/deployments/{config_id}").json() == []


def _create_pth_model(client, name: str) -> int:
    with patch("app.controllers.models._check_model_code", new=AsyncMock(return_value=True)):
        client.post("/models/", json={"name": name, "code": CODE, "framework": "pth"})
    return next(m["id"] for m in client.get("/models/").json() if m["name"] == name)


def _fake_validate_response(status_code: int, text: str = ""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    return resp


def test_import_deployment_tf_creates_a_finished_result(client):
    model_id = _create_model(client, "import-tf-model")
    client.post("/configurations/", json={"name": "import-tf-cfg", "ml_models": [model_id]})
    config_id = next(c["id"] for c in client.get("/configurations/").json() if c["name"] == "import-tf-cfg")

    with patch(
        "app.controllers.deployments.httpx.AsyncClient.post",
        new=AsyncMock(return_value=_fake_validate_response(200)),
    ) as mock_post:
        response = client.post(
            "/deployments/import",
            data={"configuration": str(config_id), "metrics": '{"train_metrics": {"accuracy": [0.9]}, "training_time": 3.5}'},
            files={"trained_model": ("model.h5", b"fake h5 bytes", "application/octet-stream")},
        )

    from app.config import settings

    assert response.status_code == 201
    # Validated against tfexecutor, not pthexecutor.
    assert mock_post.await_args.args[0] == settings.TENSORFLOW_EXECUTOR_URL + "validate_model/"

    results = client.get("/results/").json()
    result = next(r for r in results if r["model"]["id"] == model_id)
    assert result["status"] == "finished"
    assert result["train_metrics"] == {"accuracy": [0.9]}
    assert result["training_time"] == 3.5

    # The uploaded bytes actually landed on disk under the expected name.
    model_path = settings.MEDIA_ROOT / settings.TRAINED_MODELS_DIR / f"{result['id']}.h5"
    assert model_path.read_bytes() == b"fake h5 bytes"


def test_import_deployment_pth_sends_model_code_and_weights_to_pthexecutor(client):
    model_id = _create_pth_model(client, "import-pth-model")
    client.post("/configurations/", json={"name": "import-pth-cfg", "ml_models": [model_id]})
    config_id = next(c["id"] for c in client.get("/configurations/").json() if c["name"] == "import-pth-cfg")

    with patch(
        "app.controllers.deployments.httpx.AsyncClient.post",
        new=AsyncMock(return_value=_fake_validate_response(200)),
    ) as mock_post:
        response = client.post(
            "/deployments/import",
            data={"configuration": str(config_id)},
            files={"trained_model": ("weights.pth", b"fake state dict bytes", "application/octet-stream")},
        )

    assert response.status_code == 201
    from app.config import settings as _settings
    assert mock_post.await_args.args[0] == _settings.PYTORCH_EXECUTOR_URL + "validate_model/"
    assert mock_post.await_args.kwargs["data"]["model_code"] == CODE


def test_import_deployment_rejects_failed_validation_without_persisting_anything(client):
    model_id = _create_model(client, "import-bad-model")
    client.post("/configurations/", json={"name": "import-bad-cfg", "ml_models": [model_id]})
    config_id = next(c["id"] for c in client.get("/configurations/").json() if c["name"] == "import-bad-cfg")

    with patch(
        "app.controllers.deployments.httpx.AsyncClient.post",
        new=AsyncMock(return_value=_fake_validate_response(400, "not a valid keras model")),
    ):
        response = client.post(
            "/deployments/import",
            data={"configuration": str(config_id)},
            files={"trained_model": ("model.h5", b"garbage", "application/octet-stream")},
        )

    assert response.status_code == 400
    assert "failed validation" in response.json()["detail"]
    assert client.get(f"/deployments/{config_id}").json() == []


def test_import_deployment_rejects_distributed_models(client):
    with patch("app.controllers.models._check_model_code", new=AsyncMock(return_value=True)):
        # Both father and child need distributed=True - that's the real
        # contract job_manifest_generator/create_deployment already rely
        # on (only a *child*, i.e. distributed=True + father_id set, is
        # skipped when picking which model triggers a Job; the root model
        # itself still needs distributed=True to be treated as one).
        client.post(
            "/models/",
            json={"name": "import-dist-father", "code": CODE, "framework": "tf", "distributed": True},
        )
    father_id = next(m["id"] for m in client.get("/models/").json() if m["name"] == "import-dist-father")
    with patch("app.controllers.models._check_model_code", new=AsyncMock(return_value=True)):
        client.post(
            "/models/",
            json={"name": "import-dist-child", "code": CODE, "framework": "tf", "distributed": True, "father": father_id},
        )
    client.post("/configurations/", json={"name": "import-dist-cfg", "ml_models": [father_id]})
    config_id = next(c["id"] for c in client.get("/configurations/").json() if c["name"] == "import-dist-cfg")

    response = client.post(
        "/deployments/import",
        data={"configuration": str(config_id)},
        files={"trained_model": ("model.h5", b"x", "application/octet-stream")},
    )

    assert response.status_code == 400
    assert "distributed" in response.json()["detail"]


def test_import_deployment_rejects_multi_model_configurations(client):
    model_a = _create_model(client, "import-multi-a")
    model_b = _create_model(client, "import-multi-b")
    client.post("/configurations/", json={"name": "import-multi-cfg", "ml_models": [model_a, model_b]})
    config_id = next(c["id"] for c in client.get("/configurations/").json() if c["name"] == "import-multi-cfg")

    response = client.post(
        "/deployments/import",
        data={"configuration": str(config_id)},
        files={"trained_model": ("model.h5", b"x", "application/octet-stream")},
    )

    assert response.status_code == 400
    assert "exactly one model" in response.json()["detail"]


def test_import_deployment_configuration_not_found(client):
    response = client.post(
        "/deployments/import",
        data={"configuration": "999999"},
        files={"trained_model": ("model.h5", b"x", "application/octet-stream")},
    )
    assert response.status_code == 400
