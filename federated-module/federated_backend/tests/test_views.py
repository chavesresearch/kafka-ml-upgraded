"""Endpoint-level tests for create_datasource/model_from_control_logger,
ported from the original Django test_views.py - same scenarios, same
assertions, against Litestar's TestClient instead of Django's.
``deploy_on_kubernetes`` is mocked (it's now async - `AsyncMock`) since a
real collision match would otherwise try to call the real Kubernetes API.

`data_restriction`/`dataset_restrictions` are always sent as JSON-encoded
*strings* (`"{}"`), never native dicts/objects - see test_matching.py's
module docstring for why.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import engine
from app.models import Datasource, ModelSource


def _seed(*rows):
    async def _add():
        async with AsyncSession(engine) as session:
            async with session.begin():
                session.add_all(rows)

    asyncio.run(_add())


def _count(model) -> int:
    from sqlalchemy import func, select

    async def _q():
        async with AsyncSession(engine) as session:
            result = await session.execute(select(func.count()).select_from(model))
            return result.scalar_one()

    return asyncio.run(_q())


def test_create_datasource_persists_row(client):
    payload = {
        "incremental": False,
        "topic": "t1",
        "unsupervised_topic": "",
        "input_format": "RAW",
        "input_config": '{"data_reshape": "10"}',
        "description": "",
        "dataset_restrictions": "{}",
        "validation_rate": 0.2,
        "test_rate": 0.1,
        "total_msg": 100,
        "time": "2026-01-01T00:00:00",
    }

    response = client.post("/federated-datasources/", json=payload)

    assert response.status_code == 201
    assert _count(Datasource) == 1


def test_create_datasource_invalid_payload_rejected(client):
    response = client.post("/federated-datasources/", json={})
    assert response.status_code == 406
    assert _count(Datasource) == 0


@patch("app.controllers.deploy_on_kubernetes", new_callable=AsyncMock)
def test_create_datasource_matching_model_triggers_deploy(mock_deploy, client):
    _seed(
        ModelSource(
            federated_string_id="fed-1",
            input_shape="10",
            output_shape="1",
            data_restriction="{}",
            min_data=1,
            framework="tf",
            distributed=False,
            blockchain={},
        )
    )

    payload = {
        "incremental": False,
        "topic": "t1",
        "unsupervised_topic": "",
        "input_format": "RAW",
        "input_config": '{"data_reshape": "10"}',
        "description": "",
        "dataset_restrictions": "{}",
        "validation_rate": 0.2,
        "test_rate": 0.1,
        "total_msg": 100,
        "time": "2026-01-01T00:00:00",
    }

    response = client.post("/federated-datasources/", json=payload)

    assert response.status_code == 201
    mock_deploy.assert_awaited_once()
    # case=1: not distributed, not incremental, no blockchain
    assert mock_deploy.call_args.args[3] == 1
    # mark-consumed fix: the matched pair is gone after a successful match
    assert _count(ModelSource) == 0
    assert _count(Datasource) == 0


@patch("app.controllers.deploy_on_kubernetes", new_callable=AsyncMock)
def test_create_datasource_non_matching_model_does_not_deploy(mock_deploy, client):
    _seed(
        ModelSource(
            federated_string_id="fed-1",
            input_shape="999",  # mismatched shape
            output_shape="1",
            data_restriction="{}",
            min_data=1,
            framework="tf",
            distributed=False,
            blockchain={},
        )
    )

    payload = {
        "incremental": False,
        "topic": "t1",
        "unsupervised_topic": "",
        "input_format": "RAW",
        "input_config": '{"data_reshape": "10"}',
        "description": "",
        "dataset_restrictions": "{}",
        "validation_rate": 0.2,
        "test_rate": 0.1,
        "total_msg": 100,
        "time": "2026-01-01T00:00:00",
    }

    response = client.post("/federated-datasources/", json=payload)

    assert response.status_code == 201
    mock_deploy.assert_not_awaited()
    # no match - both rows survive
    assert _count(ModelSource) == 1
    assert _count(Datasource) == 1


@patch("app.controllers.deploy_on_kubernetes", new_callable=AsyncMock)
def test_model_from_control_logger_persists_and_matches_existing_datasource(mock_deploy, client):
    _seed(
        Datasource(
            incremental=False,
            topic="t1",
            input_format="RAW",
            input_config='{"data_reshape": "10"}',
            dataset_restrictions="{}",
            total_msg=100,
            time=datetime.fromisoformat("2026-01-01T00:00:00"),
        )
    )

    payload = {
        "incremental": False,
        "federated_params": {
            "federated_string_id": "fed-1",
            "data_restriction": "{}",
            "min_data": 1,
        },
        "model_format": {"input_shape": "10", "output_shape": "1"},
        "framework": "tf",
        "distributed": False,
    }

    response = client.post("/model-control-logger/", json=payload)

    assert response.status_code == 201
    mock_deploy.assert_awaited_once()
    assert _count(ModelSource) == 0
    assert _count(Datasource) == 0


@patch("app.controllers.deploy_on_kubernetes", new_callable=AsyncMock)
def test_concurrent_matching_datasources_only_deploy_once(mock_deploy, client):
    """Smoke test for `_match_lock` (app/controllers.py): two registrations
    that both match the same ModelSource, fired concurrently, must still
    only deploy once. Uses AsyncTestClient + asyncio.gather for genuine
    concurrent requests through the real ASGI app (a plain TestClient
    can't overlap two in-flight requests).

    Honest caveat, checked empirically (not assumed) before writing this
    docstring: this test currently passes **with or without** `_match_lock`
    - each handler does its own `db_session.add(...)` + `await
    db_session.flush()` (a real write) before ever reaching the match
    section, and SQLite only allows one writer transaction at a time, so
    the second concurrent request's own flush already blocks until the
    first request's entire transaction (match, deploy, delete, commit)
    finishes - the interleaving the original finding described can't
    actually occur against *this* SQLite-backed deployment. `_match_lock`
    plus committing before releasing it are kept anyway: they make the
    critical section correct on its own logical merits, independent of
    incidentally relying on SQLite's single-writer behavior - would still
    matter if this service's storage backend ever changed to something
    with real concurrent writers (e.g. Postgres). This test is real
    concurrent-request coverage either way, just not a test that would
    have failed before the fix.
    """
    import anyio
    from litestar.testing import AsyncTestClient

    from app.main import app

    async def _slow_deploy(*args, **kwargs):
        await anyio.sleep(0.05)

    mock_deploy.side_effect = _slow_deploy

    _seed(
        ModelSource(
            federated_string_id="fed-1",
            input_shape="10",
            output_shape="1",
            data_restriction="{}",
            min_data=1,
            framework="tf",
            distributed=False,
            blockchain={},
        )
    )

    def _payload(topic: str) -> dict:
        return {
            "incremental": False,
            "topic": topic,
            "unsupervised_topic": "",
            "input_format": "RAW",
            "input_config": '{"data_reshape": "10"}',
            "description": "",
            "dataset_restrictions": "{}",
            "validation_rate": 0.2,
            "test_rate": 0.1,
            "total_msg": 100,
            "time": "2026-01-01T00:00:00",
        }

    async def _fire_both():
        async with AsyncTestClient(app=app) as async_client:
            return await asyncio.gather(
                async_client.post("/federated-datasources/", json=_payload("t1")),
                async_client.post("/federated-datasources/", json=_payload("t2")),
            )

    responses = asyncio.run(_fire_both())

    assert all(r.status_code == 201 for r in responses)
    # Exactly one of the two requests found the ModelSource still there -
    # the other's fresh SELECT (its own AsyncSession) must see it already
    # gone, not race it into a second, duplicate deploy.
    assert mock_deploy.await_count == 1
    assert _count(ModelSource) == 0
    # The matched request's own Datasource was deleted alongside the
    # ModelSource; the other request's Datasource never matched anything
    # (by the time its locked section ran) and survives.
    assert _count(Datasource) == 1
