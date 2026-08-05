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
