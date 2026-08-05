"""Regression test for app/kubernetes_deploy.py's deploy_on_kubernetes()
security hardening (FUTURE.md's exec() sandboxing pass) - the edge worker
Job it builds must carry a non-root/no-capabilities/seccomp
securityContext, same as ../../../backend/app/job_manifest_generator.py's
manifests. Ported from the original Django test_deploy_on_kubernetes.py.

Mocks config.load_incluster_config (would raise outside a real cluster)
and client.BatchV1Api - this test never talks to a real Kubernetes API,
it only inspects the manifest dict passed to create_namespaced_job.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.kubernetes_deploy import deploy_on_kubernetes


@patch("app.kubernetes_deploy.client.BatchV1Api")
@patch("app.kubernetes_deploy.k8s_config.load_incluster_config")
def test_deploy_on_kubernetes_job_is_hardened(mock_load_config, mock_batch_api_cls):
    mock_api_instance = MagicMock()
    mock_api_instance.create_namespaced_job = AsyncMock()
    mock_batch_api_cls.return_value = mock_api_instance

    datasource_item = {
        "topic": "t1",
        "unsupervised_topic": "",
        "input_format": "RAW",
        "input_config": "{}",
        "validation_rate": 0.2,
        "test_rate": 0.1,
        "total_msg": 100,
    }
    model_item = {"federated_string_id": "fed-1"}

    asyncio.run(deploy_on_kubernetes(datasource_item, model_item, framework="tf", case=1))

    assert mock_api_instance.create_namespaced_job.await_args is not None
    job_manifest = mock_api_instance.create_namespaced_job.await_args.kwargs["body"]
    template = job_manifest["spec"]["template"]
    assert template["metadata"]["labels"]["app"] == "kafka-ml-training"
    pod_spec = template["spec"]

    assert pod_spec["securityContext"] == {"seccompProfile": {"type": "RuntimeDefault"}}
    container = pod_spec["containers"][0]
    assert container["securityContext"] == {
        "runAsNonRoot": True,
        "runAsUser": 1000,
        "allowPrivilegeEscalation": False,
        "capabilities": {"drop": ["ALL"]},
    }
