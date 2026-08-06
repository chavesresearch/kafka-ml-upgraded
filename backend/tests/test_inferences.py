"""stop_inference must not silently mark a row "stopped" when the real
Kubernetes delete failed - see FUTURE.md/CLAUDE.md for the bug this fixes:
a bare `except Exception: pass` used to swallow every K8s error and set
status="stopped" unconditionally, orphaning the still-running
ReplicationController with no way to retry (stop requires
status=="deployed", delete requires "stopped", so the row became
unreachable via this API forever).

Mocks kubernetes_api_client/load_incluster_config - same reasoning as
test_models.py mocking `_check_model_code`, this is the one genuinely
external call these tests would otherwise need a live cluster for.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from kubernetes_asyncio.client.exceptions import ApiException

from app.db import async_session_maker
from app.models import Inference


async def _seed_deployed_inference_async(name_prefix: str) -> int:
    async with async_session_maker() as session:
        async with session.begin():
            inference = Inference(status="deployed")
            session.add(inference)
            await session.flush()
            return inference.id


def _seed_deployed_inference(name_prefix: str) -> int:
    return asyncio.run(_seed_deployed_inference_async(name_prefix))


def _mock_api_client_raising(exc: Exception):
    """A context-manager-compatible fake standing in for
    kubernetes_api_client(...)'s return value, whose delete call raises `exc`."""
    api_instance = MagicMock()
    api_instance.delete_namespaced_replication_controller = AsyncMock(side_effect=exc)

    fake_client = MagicMock()
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)
    return fake_client, api_instance


def test_stop_inference_marks_stopped_when_rc_already_gone(client):
    inference_id = _seed_deployed_inference("stop-404")
    fake_client, api_instance = _mock_api_client_raising(
        ApiException(status=404, reason="Not Found")
    )

    with (
        patch("app.controllers.inferences.k8s_config.load_incluster_config"),
        patch("app.controllers.inferences.kubernetes_api_client", return_value=fake_client),
        patch("app.controllers.inferences.k8s_client.CoreV1Api", return_value=api_instance),
    ):
        response = client.post(f"/inferences/{inference_id}")

    assert response.status_code == 200

    get_response = client.get("/inferences/")
    stopped = next(i for i in get_response.json() if i["id"] == inference_id)
    assert stopped["status"] == "stopped"


def test_stop_inference_does_not_mark_stopped_on_real_k8s_failure(client):
    inference_id = _seed_deployed_inference("stop-500")
    fake_client, api_instance = _mock_api_client_raising(
        ApiException(status=500, reason="Internal Server Error")
    )

    with (
        patch("app.controllers.inferences.k8s_config.load_incluster_config"),
        patch("app.controllers.inferences.kubernetes_api_client", return_value=fake_client),
        patch("app.controllers.inferences.k8s_client.CoreV1Api", return_value=api_instance),
    ):
        response = client.post(f"/inferences/{inference_id}")

    assert response.status_code == 502

    get_response = client.get("/inferences/")
    still_deployed = next(i for i in get_response.json() if i["id"] == inference_id)
    assert still_deployed["status"] == "deployed"
