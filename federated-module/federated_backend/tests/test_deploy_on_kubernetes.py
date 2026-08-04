"""Regression test for automl/views.py's deploy_on_kubernetes() security
hardening (FUTURE.md's exec() sandboxing pass) - the edge worker Job it
builds must carry a non-root/no-capabilities/seccomp securityContext, same
as ../../../backend/app/job_manifest_generator.py's manifests.

Mocks config.load_incluster_config (would raise outside a real cluster)
and client.BatchV1Api - this test never talks to a real Kubernetes API,
it only inspects the manifest dict passed to create_namespaced_job.
"""

from unittest.mock import MagicMock, patch

from automl.views import deploy_on_kubernetes


@patch("automl.views.client.BatchV1Api")
@patch("automl.views.config.load_incluster_config")
def test_deploy_on_kubernetes_job_is_hardened(mock_load_config, mock_batch_api_cls):
    mock_api_instance = MagicMock()
    mock_batch_api_cls.return_value = mock_api_instance

    datasource_item = {
        "topic": "t1",
        "unsupervised_topic": "",
        "input_format": "RAW",
        "input_config": "{}",
        "validation_rate": "0.2",
        "test_rate": "0.1",
        "total_msg": 100,
    }
    model_item = {"federated_string_id": "fed-1"}

    deploy_on_kubernetes(datasource_item, model_item, framework="tf", case=1)

    assert mock_api_instance.create_namespaced_job.called
    job_manifest = mock_api_instance.create_namespaced_job.call_args.kwargs["body"]
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
