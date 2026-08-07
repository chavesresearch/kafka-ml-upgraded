"""MLModel CRUD, including distributed father/child creation and update -
mirrors the themes covered by the old Django `ModelViewTest`
(`../../kafka-ml/backend/automl/test_views.py`), rewritten against this
port's actual, current contract (confirmed against `app/schemas/
__init__.py`'s `model_dict` and `app/controllers/models.py`).

`_check_model_code` (the live call to tfexecutor/pthexecutor) is mocked
throughout, per `CLAUDE.md`'s own documented testing approach - these
tests exercise the backend's own logic, not the ML code executor
services.
"""

from unittest.mock import AsyncMock, patch

CODE = 'model = "not real code, _check_model_code is mocked"'


def _mock_valid():
    return patch("app.controllers.models._check_model_code", new=AsyncMock(return_value=True))


def _mock_invalid():
    return patch("app.controllers.models._check_model_code", new=AsyncMock(return_value=False))


def test_create_and_get_model(client):
    with _mock_valid():
        resp = client.post("/models/", json={"name": "test-create", "code": CODE, "framework": "tf"})
    assert resp.status_code == 201

    models = client.get("/models/").json()
    match = next(m for m in models if m["name"] == "test-create")
    assert match["code"] == CODE
    assert match["framework"] == "tf"
    assert match["distributed"] is False
    assert match["father"] is None

    resp = client.get(f"/models/{match['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "test-create"
    assert match["created_at"] is not None
    assert match["updated_at"] is not None


def test_create_model_fails_validation(client):
    with _mock_invalid():
        resp = client.post("/models/", json={"name": "test-invalid", "code": "bad", "framework": "tf"})
    assert resp.status_code == 400
    assert not any(m["name"] == "test-invalid" for m in client.get("/models/").json())


def test_update_model(client):
    with _mock_valid():
        client.post("/models/", json={"name": "test-update", "code": CODE, "framework": "tf"})
    model_id = next(m["id"] for m in client.get("/models/").json() if m["name"] == "test-update")

    with _mock_valid():
        resp = client.put(f"/models/{model_id}", json={"name": "test-updated", "code": CODE, "framework": "tf"})
    assert resp.status_code == 200

    created = client.get(f"/models/{model_id}").json()
    with _mock_valid():
        resp = client.put(
            f"/models/{model_id}", json={"name": "test-updated-again", "code": CODE, "framework": "tf"}
        )
    assert resp.status_code == 200
    updated = client.get(f"/models/{model_id}").json()
    assert updated["name"] == "test-updated-again"
    assert updated["created_at"] == created["created_at"]
    assert updated["updated_at"] >= created["updated_at"]


def test_delete_model(client):
    with _mock_valid():
        client.post("/models/", json={"name": "test-delete", "code": CODE, "framework": "tf"})
    model_id = next(m["id"] for m in client.get("/models/").json() if m["name"] == "test-delete")

    resp = client.delete(f"/models/{model_id}")
    assert resp.status_code == 200
    assert not any(m["id"] == model_id for m in client.get("/models/").json())


def test_delete_model_not_found(client):
    resp = client.delete("/models/999999")
    assert resp.status_code == 400


def test_create_distributed_father_child(client):
    with _mock_valid():
        resp = client.post(
            "/models/", json={"name": "test-father", "code": CODE, "framework": "tf", "distributed": True}
        )
    assert resp.status_code == 201
    father_id = next(m["id"] for m in client.get("/models/").json() if m["name"] == "test-father")

    with _mock_valid():
        resp = client.post(
            "/models/",
            json={
                "name": "test-child",
                "code": CODE,
                "framework": "tf",
                "distributed": True,
                "father": father_id,
            },
        )
    assert resp.status_code == 201

    child = next(m for m in client.get("/models/").json() if m["name"] == "test-child")
    assert child["father"] == {"id": father_id, "name": "test-father", "framework": "tf"}

    distributed = client.get("/models/distributed").json()
    assert {m["name"] for m in distributed} >= {"test-father", "test-child"}

    fathers = client.get("/models/fathers").json()
    assert any(m["name"] == "test-father" for m in fathers)
    assert not any(m["name"] == "test-child" for m in fathers)


def test_update_distributed_sets_father(client):
    with _mock_valid():
        client.post("/models/", json={"name": "test-father2", "code": CODE, "framework": "tf", "distributed": True})
        client.post("/models/", json={"name": "test-child2", "code": CODE, "framework": "tf", "distributed": True})
    models = client.get("/models/").json()
    father_id = next(m["id"] for m in models if m["name"] == "test-father2")
    child_id = next(m["id"] for m in models if m["name"] == "test-child2")

    with _mock_valid():
        resp = client.put(
            f"/models/{child_id}",
            json={
                "name": "test-child2",
                "code": CODE,
                "framework": "tf",
                "distributed": True,
                "father": father_id,
            },
        )
    assert resp.status_code == 200

    updated = client.get(f"/models/{child_id}").json()
    assert updated["father"]["id"] == father_id
