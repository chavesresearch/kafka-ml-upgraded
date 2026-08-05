"""Tests for KafkaMLClient against a fake in-memory backend (see
conftest.py) - covers the client's own logic (id lookup after create,
before/after id diffing, error wrapping, polling), not the real backend's
behavior (that's backend/tests' job)."""

import httpx
import pytest

from kafkaml_client import KafkaMLClient, KafkaMLError


# -- error wrapping --------------------------------------------------------


def test_error_response_raises_kafkaml_error_with_status_and_body():
    def handler(request):
        return httpx.Response(400, text="bad request body")

    c = KafkaMLClient(base_url="http://backend")
    c._http = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://backend")
    with pytest.raises(KafkaMLError) as exc_info:
        c.list_models()
    assert exc_info.value.status_code == 400
    assert exc_info.value.response_text == "bad request body"


def test_success_response_does_not_raise():
    def handler(request):
        return httpx.Response(200, json=[])

    c = KafkaMLClient(base_url="http://backend")
    c._http = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://backend")
    assert c.list_models() == []


# -- models -----------------------------------------------------------------


def test_create_model_looks_up_the_new_id_by_name(client):
    model_id = client.create_model(name="my-model", code="model = ...", framework="tf")
    assert model_id == 1
    assert client.get_model(model_id)["name"] == "my-model"


def test_create_model_with_father_sends_it_through(client, backend):
    root_id = client.create_model(name="root", code="...", framework="tf", distributed=True)
    child_id = client.create_model(name="child", code="...", framework="tf", distributed=True, father=root_id)
    assert backend.models[1]["father"] == root_id
    assert child_id != root_id


def test_create_model_raises_if_not_found_after_create(monkeypatch):
    """Defensive edge case: if the backend's list endpoint doesn't
    reflect what was just created (e.g. a race, or the name didn't
    match), the client should raise a clear error, not silently return a
    wrong id."""

    def handler(request):
        if request.method == "POST":
            return httpx.Response(201)
        return httpx.Response(200, json=[])  # never actually contains the new model

    c = KafkaMLClient(base_url="http://backend")
    c._http = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://backend")
    with pytest.raises(KafkaMLError, match="not found"):
        c.create_model(name="ghost", code="...", framework="tf")


def test_list_and_delete_model(client):
    model_id = client.create_model(name="m1", code="...", framework="tf")
    assert len(client.list_models()) == 1
    client.delete_model(model_id)
    assert client.list_models() == []


# -- configurations -----------------------------------------------------------


def test_create_configuration_looks_up_the_new_id_by_name(client):
    model_id = client.create_model(name="m1", code="...", framework="tf")
    config_id = client.create_configuration(name="my-config", model_ids=[model_id])
    assert client.get_configuration(config_id)["ml_models"] == [model_id]


def test_delete_configuration(client):
    model_id = client.create_model(name="m1", code="...", framework="tf")
    config_id = client.create_configuration(name="cfg", model_ids=[model_id])
    client.delete_configuration(config_id)
    assert client.list_configurations() == []


# -- deployments --------------------------------------------------------------


def test_create_deployment_diffs_ids_to_find_the_new_one(client):
    model_id = client.create_model(name="m1", code="...", framework="tf")
    config_id = client.create_configuration(name="cfg", model_ids=[model_id])
    deployment_id = client.create_deployment(configuration=config_id, batch=4, tf_kwargs_fit="epochs=1")
    assert deployment_id in {d["id"] for d in client.list_deployments()}


def test_create_deployment_passes_arbitrary_fields_through(client, backend):
    model_id = client.create_model(name="m1", code="...", framework="tf")
    config_id = client.create_configuration(name="cfg", model_ids=[model_id])
    client.create_deployment(
        configuration=config_id,
        batch=4,
        incremental=True,
        stream_timeout=30000,
        federated=False,
    )
    assert backend.deployments[0]["incremental"] is True
    assert backend.deployments[0]["stream_timeout"] == 30000


def test_create_deployment_raises_if_no_new_id_appears():
    def handler(request):
        if request.method == "POST":
            return httpx.Response(201)
        return httpx.Response(200, json=[])

    c = KafkaMLClient(base_url="http://backend")
    c._http = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://backend")
    with pytest.raises(KafkaMLError, match="no new id found"):
        c.create_deployment(configuration=1, batch=1)


def test_delete_deployment(client):
    model_id = client.create_model(name="m1", code="...", framework="tf")
    config_id = client.create_configuration(name="cfg", model_ids=[model_id])
    deployment_id = client.create_deployment(configuration=config_id, batch=1)
    client.delete_deployment(deployment_id)
    assert client.list_deployments() == []


# -- results ------------------------------------------------------------------


def test_list_results_filters_by_deployment_id(client, backend):
    backend.results.extend(
        [
            {"id": 1, "deployment": {"id": 10}, "status": "finished"},
            {"id": 2, "deployment": {"id": 20}, "status": "finished"},
        ]
    )
    filtered = client.list_results(deployment_id=10)
    assert [r["id"] for r in filtered] == [1]


def test_get_result_returns_the_matching_row(client, backend):
    backend.results.append({"id": 5, "deployment": {"id": 1}, "status": "finished"})
    assert client.get_result(5)["status"] == "finished"


def test_get_result_raises_when_missing(client):
    with pytest.raises(KafkaMLError, match="not found"):
        client.get_result(999)


def test_wait_for_results_returns_once_status_matches(client, backend):
    backend.results.append({"id": 1, "deployment": {"id": 10}, "status": "deployed"})

    # Flip to "finished" after the first poll, simulating a real
    # in-progress-then-done training run.
    original_list = client.list_results
    calls = {"n": 0}

    def flipping_list_results(deployment_id=None):
        calls["n"] += 1
        if calls["n"] >= 2:
            backend.results[0]["status"] = "finished"
        return original_list(deployment_id)

    client.list_results = flipping_list_results
    results = client.wait_for_results(10, status="finished", timeout=5, poll_interval=0.01)
    assert results[0]["status"] == "finished"
    assert calls["n"] >= 2


def test_wait_for_results_times_out_if_status_never_reached(client, backend):
    backend.results.append({"id": 1, "deployment": {"id": 10}, "status": "deployed"})
    with pytest.raises(TimeoutError, match="did not reach status"):
        client.wait_for_results(10, status="finished", timeout=0.05, poll_interval=0.01)


def test_wait_for_results_requires_min_results_count(client, backend):
    """A distributed deployment produces one result per submodel -
    min_results should gate on that count, not just the first result's
    status."""
    backend.results.append({"id": 1, "deployment": {"id": 10}, "status": "finished"})
    with pytest.raises(TimeoutError):
        client.wait_for_results(10, status="finished", timeout=0.05, poll_interval=0.01, min_results=2)


# -- inference ------------------------------------------------------------------


def test_deploy_inference_diffs_ids_to_find_the_new_one(client):
    inference_id = client.deploy_inference(
        result_id=1, input_topic="in-topic", output_topic="out-topic", replicas=1
    )
    assert inference_id in {i["id"] for i in client.list_inferences()}


def test_deploy_inference_raises_if_no_new_id_appears():
    def handler(request):
        if request.method == "POST":
            return httpx.Response(201)
        return httpx.Response(200, json=[])

    c = KafkaMLClient(base_url="http://backend")
    c._http = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://backend")
    with pytest.raises(KafkaMLError, match="no new id found"):
        c.deploy_inference(result_id=1, input_topic="in", output_topic="out")


def test_stop_and_delete_inference(client):
    inference_id = client.deploy_inference(result_id=1, input_topic="in", output_topic="out")
    client.stop_inference(inference_id)  # should not raise (200, not the 201 default)
    client.delete_inference(inference_id)
    assert client.list_inferences() == []


# -- context manager / lifecycle -------------------------------------------------


def test_context_manager_closes_the_http_client():
    def handler(request):
        return httpx.Response(200, json=[])

    c = KafkaMLClient(base_url="http://backend")
    c._http = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://backend")
    with c as ctx:
        assert ctx is c
        assert c._http.is_closed is False
    assert c._http.is_closed is True


def test_close_is_idempotent_enough_to_call_directly():
    def handler(request):
        return httpx.Response(200, json=[])

    c = KafkaMLClient(base_url="http://backend")
    c._http = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://backend")
    c.close()
    assert c._http.is_closed is True
