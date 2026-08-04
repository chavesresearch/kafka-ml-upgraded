"""Endpoint-level tests for DatasourceList/ModelFromControlLogger, using
Django's real test client + test database (pytest-django's django_db
fixture) - no live Kafka/Kubernetes needed. `deploy_on_kubernetes` is
mocked (same spirit as ../../../backend/CLAUDE.md's `_check_model_code`
mocking pattern) since a real collision match would otherwise try to call
the real Kubernetes API.

`data_restriction`/`dataset_restrictions` are always sent as JSON-encoded
*strings* (`"{}"`), never native dicts/objects - see
test_check_colission.py's module docstring for why: check_colission()
calls json.loads() on both, which crashes on an already-decoded dict.
First-hand confirmed this by initially writing these payloads with native
`{}` and hitting exactly the TypeError CLAUDE.md describes, before fixing
the test payloads to match the real wire format.
"""

import json
from unittest.mock import patch

import pytest

from automl.models import Datasource, ModelSource


@pytest.mark.django_db
def test_create_datasource_persists_row(client):
    payload = {
        "incremental": False,
        "topic": "t1",
        "unsupervised_topic": "",
        "input_format": "RAW",
        "input_config": '{"data_reshape": "10"}',
        "description": "",
        "dataset_restrictions": "{}",
        "validation_rate": "0.2",
        "test_rate": "0.1",
        "total_msg": 100,
        "time": "2026-01-01T00:00:00Z",
    }

    response = client.post(
        "/federated-datasources/", data=json.dumps(payload), content_type="application/json"
    )

    assert response.status_code == 201
    assert Datasource.objects.count() == 1
    assert Datasource.objects.get().topic == "t1"


@pytest.mark.django_db
def test_create_datasource_invalid_payload_rejected(client):
    response = client.post(
        "/federated-datasources/", data=json.dumps({}), content_type="application/json"
    )
    assert response.status_code == 406
    assert Datasource.objects.count() == 0


@pytest.mark.django_db
@patch("automl.views.deploy_on_kubernetes")
def test_create_datasource_matching_model_triggers_deploy(mock_deploy, client):
    ModelSource.objects.create(
        federated_string_id="fed-1",
        input_shape="10",
        output_shape="1",
        data_restriction="{}",
        min_data=1,
        framework="tf",
        distributed=False,
        blockchain={},
    )

    payload = {
        "incremental": False,
        "topic": "t1",
        "unsupervised_topic": "",
        "input_format": "RAW",
        "input_config": '{"data_reshape": "10"}',
        "description": "",
        "dataset_restrictions": "{}",
        "validation_rate": "0.2",
        "test_rate": "0.1",
        "total_msg": 100,
        "time": "2026-01-01T00:00:00Z",
    }

    response = client.post(
        "/federated-datasources/", data=json.dumps(payload), content_type="application/json"
    )

    assert response.status_code == 201
    mock_deploy.assert_called_once()
    # case=1: not distributed, not incremental, no blockchain
    assert mock_deploy.call_args.args[3] == 1


@pytest.mark.django_db
@patch("automl.views.deploy_on_kubernetes")
def test_create_datasource_non_matching_model_does_not_deploy(mock_deploy, client):
    ModelSource.objects.create(
        federated_string_id="fed-1",
        input_shape="999",  # mismatched shape
        output_shape="1",
        data_restriction="{}",
        min_data=1,
        framework="tf",
        distributed=False,
        blockchain={},
    )

    payload = {
        "incremental": False,
        "topic": "t1",
        "unsupervised_topic": "",
        "input_format": "RAW",
        "input_config": '{"data_reshape": "10"}',
        "description": "",
        "dataset_restrictions": "{}",
        "validation_rate": "0.2",
        "test_rate": "0.1",
        "total_msg": 100,
        "time": "2026-01-01T00:00:00Z",
    }

    response = client.post(
        "/federated-datasources/", data=json.dumps(payload), content_type="application/json"
    )

    assert response.status_code == 201
    mock_deploy.assert_not_called()


@pytest.mark.django_db
@patch("automl.views.deploy_on_kubernetes")
def test_model_from_control_logger_persists_and_matches_existing_datasource(mock_deploy, client):
    Datasource.objects.create(
        incremental=False,
        topic="t1",
        input_format="RAW",
        input_config='{"data_reshape": "10"}',
        dataset_restrictions="{}",
        total_msg=100,
        time="2026-01-01T00:00:00Z",
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

    response = client.post(
        "/model-control-logger/", data=json.dumps(payload), content_type="application/json"
    )

    assert response.status_code == 201
    assert ModelSource.objects.count() == 1
    mock_deploy.assert_called_once()
