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
