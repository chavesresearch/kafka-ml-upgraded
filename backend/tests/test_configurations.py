"""Configuration CRUD - mirrors the old Django `ConfigurationViewTest`
themes, against this port's real `/configurations/` contract."""

from unittest.mock import AsyncMock, patch

CODE = 'model = "not real code, _check_model_code is mocked"'


def _create_model(client, name: str) -> int:
    with patch("app.controllers.models._check_model_code", new=AsyncMock(return_value=True)):
        client.post("/models/", json={"name": name, "code": CODE, "framework": "tf"})
    return next(m["id"] for m in client.get("/models/").json() if m["name"] == name)


def test_create_and_get_configuration(client):
    model_id = _create_model(client, "cfg-model-1")

    resp = client.post(
        "/configurations/",
        json={"name": "cfg-test-1", "description": "desc", "ml_models": [model_id]},
    )
    assert resp.status_code == 201

    configs = client.get("/configurations/").json()
    match = next(c for c in configs if c["name"] == "cfg-test-1")
    assert match["description"] == "desc"
    assert [m["id"] for m in match["ml_models"]] == [model_id]
    assert match["deployments"] == []


def test_update_configuration(client):
    model_a = _create_model(client, "cfg-model-2a")
    model_b = _create_model(client, "cfg-model-2b")

    client.post("/configurations/", json={"name": "cfg-test-2", "ml_models": [model_a]})
    config_id = next(c["id"] for c in client.get("/configurations/").json() if c["name"] == "cfg-test-2")

    resp = client.put(
        f"/configurations/{config_id}",
        json={"name": "cfg-test-2-renamed", "description": "new desc", "ml_models": [model_b]},
    )
    assert resp.status_code == 200

    updated = client.get(f"/configurations/{config_id}").json()
    assert updated["name"] == "cfg-test-2-renamed"
    assert updated["description"] == "new desc"
    assert [m["id"] for m in updated["ml_models"]] == [model_b]


def test_delete_configuration(client):
    model_id = _create_model(client, "cfg-model-3")
    client.post("/configurations/", json={"name": "cfg-test-3", "ml_models": [model_id]})
    config_id = next(c["id"] for c in client.get("/configurations/").json() if c["name"] == "cfg-test-3")

    resp = client.delete(f"/configurations/{config_id}")
    assert resp.status_code == 200
    assert not any(c["id"] == config_id for c in client.get("/configurations/").json())


def test_delete_configuration_not_found(client):
    resp = client.delete("/configurations/999999")
    assert resp.status_code == 400


def test_distributed_model_expands_to_child(client):
    """A configuration created from just the *root* (father-less) model id
    should automatically pull in its child - `_expand_with_children` in
    `app/controllers/configurations.py`."""
    with patch("app.controllers.models._check_model_code", new=AsyncMock(return_value=True)):
        client.post("/models/", json={"name": "cfg-father", "code": CODE, "framework": "tf", "distributed": True})
    father_id = next(m["id"] for m in client.get("/models/").json() if m["name"] == "cfg-father")

    with patch("app.controllers.models._check_model_code", new=AsyncMock(return_value=True)):
        client.post(
            "/models/",
            json={"name": "cfg-child", "code": CODE, "framework": "tf", "distributed": True, "father": father_id},
        )
    child_id = next(m["id"] for m in client.get("/models/").json() if m["name"] == "cfg-child")

    resp = client.post("/configurations/", json={"name": "cfg-test-4", "ml_models": [father_id]})
    assert resp.status_code == 201

    match = next(c for c in client.get("/configurations/").json() if c["name"] == "cfg-test-4")
    assert {m["id"] for m in match["ml_models"]} == {father_id, child_id}
