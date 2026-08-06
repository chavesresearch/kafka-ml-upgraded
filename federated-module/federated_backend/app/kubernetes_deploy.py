import json
import logging
import os
from typing import Any
from uuid import uuid4

from kubernetes_asyncio import client, config as k8s_config

from app.config import settings

logger = logging.getLogger(__name__)


def kubernetes_api_client(token: str | None = None, external_host: str | None = None) -> client.ApiClient:
    """Builds a Kubernetes API client.

    You can provide a token and the external host IP to access an external
    Kubernetes cluster. If one of them is not provided, the configuration
    returned targets the local/in-cluster machine (set up by
    ``kubernetes_asyncio.config.load_incluster_config`` beforehand).

    Byte-identical fix to ../../../backend/app/utils.py's own
    ``kubernetes_api_client`` (itself fixing the same bug independently
    found in this service's original Django ``kubernetes_config()``) -
    ``client.Configuration()``'s bare constructor does *not* inherit
    whatever ``load_incluster_config()`` registered as the process-wide
    default; it hardcodes ``self._base_path = "http://localhost"``
    unconditionally when no ``host`` kwarg is given. ``ApiClient()`` with
    *no* Configuration argument does the right thing - it resolves
    ``Configuration.get_default_copy()`` internally, which does pick up
    the in-cluster default.
    """
    if token is not None and external_host is not None:
        configuration = client.Configuration()
        configuration.host = external_host
        configuration.verify_ssl = False
        configuration.api_key = {"authorization": "Bearer " + token}
        return client.ApiClient(configuration)
    return client.ApiClient()


async def deploy_on_kubernetes(
    datasource_item: dict[str, Any], model_item: dict[str, Any], framework: str, case: int
) -> None:
    """Creates a real Kubernetes Job for a matched (datasource, model) pair.

    Ported from the original Django ``deploy_on_kubernetes`` - same Job
    manifest shape, same security hardening (see
    tests/test_kubernetes_deploy.py), same per-case env vars. Errors here
    are logged and swallowed, not raised - matching the original's own
    behavior of not failing the parent registration request just because
    a deploy attempt failed (the ModelSource/Datasource registration
    itself is a separate, already-committed concern by the time this
    runs - see app/controllers.py).
    """
    try:
        k8s_config.load_incluster_config()
        api_client = kubernetes_api_client(token=os.environ.get("KUBE_TOKEN"), external_host=os.environ.get("KUBE_HOST"))
        async with api_client:
            batch_api = client.BatchV1Api(api_client)

            if framework == "tf":
                image = settings.TENSORFLOW_FEDERATED_TRAINING_MODEL_IMAGE
            elif framework == "pth":
                image = settings.PYTORCH_FEDERATED_TRAINING_MODEL_IMAGE
            else:
                raise NotImplementedError("Framework/metodology not implemented")

            federated_model_id = str(model_item["federated_string_id"])
            federated_client_id = str(uuid4().hex[:8])

            job_manifest = {
                "apiVersion": "batch/v1",
                "kind": "Job",
                "metadata": {"name": f"federated-training-{federated_model_id}-worker-{federated_client_id}"},
                "spec": {
                    "ttlSecondsAfterFinished": 10,
                    "template": {
                        "metadata": {"labels": {"app": "kafka-ml-training"}},
                        "spec": {
                            "securityContext": {"seccompProfile": {"type": "RuntimeDefault"}},
                            "containers": [
                                {
                                    "image": image,
                                    "name": "training",
                                    "securityContext": {
                                        "runAsNonRoot": True,
                                        "runAsUser": 1000,
                                        "allowPrivilegeEscalation": False,
                                        "capabilities": {"drop": ["ALL"]},
                                    },
                                    "env": [
                                        {"name": "KML_CLOUD_BOOTSTRAP_SERVERS", "value": settings.KML_CLOUD_BOOTSTRAP_SERVERS},
                                        {"name": "DATA_BOOTSTRAP_SERVERS", "value": settings.FEDERATED_BOOTSTRAP_SERVERS},
                                        {"name": "DATA_TOPIC", "value": datasource_item["topic"]},
                                        {"name": "UNSUPERVISED_TOPIC", "value": datasource_item["unsupervised_topic"]},
                                        {"name": "INPUT_FORMAT", "value": datasource_item["input_format"]},
                                        {"name": "INPUT_CONFIG", "value": datasource_item["input_config"]},
                                        {"name": "VALIDATION_RATE", "value": str(datasource_item["validation_rate"])},
                                        {"name": "TEST_RATE", "value": str(datasource_item["test_rate"])},
                                        {"name": "TOTAL_MSG", "value": str(datasource_item["total_msg"])},
                                        {"name": "FEDERATED_MODEL_ID", "value": federated_model_id},
                                        {"name": "FEDERATED_CLIENT_ID", "value": federated_client_id},
                                        {"name": "NVIDIA_VISIBLE_DEVICES", "value": "all"},
                                        {"name": "CASE", "value": str(case)},
                                    ],
                                }
                            ],
                            "imagePullPolicy": "Always",
                            "restartPolicy": "OnFailure",
                        },
                    },
                },
            }

            if case == 5:
                env = job_manifest["spec"]["template"]["spec"]["containers"][0]["env"]
                env.append({"name": "ETH_RPC_URL", "value": model_item["blockchain"]["rpc_url"]})
                env.append({"name": "ETH_CONTRACT_ADDRESS", "value": model_item["blockchain"]["contract_address"]})
                env.append({"name": "ETH_CONTRACT_ABI", "value": json.dumps(model_item["blockchain"]["contract_abi"])})
                env.append({"name": "ETH_WALLET_ADDRESS", "value": os.environ.get("FEDML_BLOCKCHAIN_WALLET_ADDRESS")})
                # A private key, not config - point the edge worker at the
                # same Secret this process's own copy came from, rather than
                # copying the resolved value as plaintext into a Job manifest
                # for code this service doesn't trust. See
                # federated-backend-deployment.yaml's own FEDML_BLOCKCHAIN_WALLET_KEY.
                env.append(
                    {
                        "name": "ETH_WALLET_KEY",
                        "valueFrom": {
                            "secretKeyRef": {
                                "name": "kafkaml-blockchain-credentials",
                                "key": "wallet-key",
                                "optional": True,
                            }
                        },
                    }
                )

            logger.debug("Job manifest: %s", job_manifest)
            resp = await batch_api.create_namespaced_job(body=job_manifest, namespace=settings.KUBE_NAMESPACE)
            logger.info("Job created. status='%s'", resp.status)
    except Exception as e:
        logger.error("Error deploying to kubernetes: %s", str(e))
