import json
import logging
import os
import re
from typing import Any

import httpx
from kubernetes_asyncio import client as k8s_client, config as k8s_config
from litestar import Router, get, post, delete
from litestar.exceptions import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models import Datasource, Inference, MLModel, TrainingResult
from app.schemas import inference_dict
from app.utils import is_blank, kubernetes_api_client

logger = logging.getLogger(__name__)


@get("/inferences/", tags=["inferences"])
async def list_inferences(db_session: AsyncSession) -> list[dict[str, Any]]:
    result = await db_session.execute(select(Inference))
    return [inference_dict(i) for i in result.scalars().all()]


@get("/inferences/{inference_id:int}", tags=["inferences"])
async def get_inference(inference_id: int, db_session: AsyncSession) -> dict[str, Any]:
    inference = await db_session.get(Inference, inference_id)
    if inference is None:
        raise HTTPException(status_code=400, detail="Inference does not exist")
    return inference_dict(inference)


@post("/inferences/{inference_id:int}", tags=["inferences"], status_code=200)
async def stop_inference(inference_id: int, db_session: AsyncSession) -> None:
    inference = await db_session.get(Inference, inference_id)
    if inference is None or inference.status != "deployed":
        raise HTTPException(status_code=400, detail="Inference not found or not running")

    try:
        # kubernetes_asyncio.config.load_incluster_config is sync in
        # kubernetes-asyncio==32.0.0 - see deployments.py's create_deployment
        # for the full explanation of this real, found-via-testing bug.
        k8s_config.load_incluster_config()

        if not is_blank(inference.external_host) and not is_blank(inference.token):
            token, external_host = inference.token, inference.external_host
        else:
            token = os.environ.get("KUBE_TOKEN")
            external_host = os.environ.get("KUBE_HOST")

        api_client = kubernetes_api_client(token=token, external_host=external_host)
        async with api_client:
            api_instance = k8s_client.CoreV1Api(api_client)
            await api_instance.delete_namespaced_replication_controller(
                name=f"model-inference-{inference.id}",
                namespace=settings.KUBE_NAMESPACE,
                body=k8s_client.V1DeleteOptions(
                    propagation_policy="Foreground", grace_period_seconds=5
                ),
            )
    except Exception:
        pass

    inference.status = "stopped"


@delete("/inferences/{inference_id:int}", tags=["inferences"], status_code=200)
async def delete_inference(inference_id: int, db_session: AsyncSession) -> None:
    inference = await db_session.get(Inference, inference_id)
    if inference is None:
        raise HTTPException(status_code=400, detail="Inference does not exist")
    if inference.status != "stopped":
        raise HTTPException(
            status_code=400, detail="Inference in use, please stop it before delete."
        )
    await db_session.delete(inference)


@get("/results/inference/{result_id:int}", tags=["inferences"])
async def suggest_inference_config(result_id: int, db_session: AsyncSession, http_client: httpx.AsyncClient) -> dict[str, Any]:
    """Checks if the training result exists and returns the input format and
    configuration if there is any in another inference or datasource object,
    to pre-fill the inference deployment form."""
    result = await db_session.get(
        TrainingResult, result_id, options=[selectinload(TrainingResult.model)]
    )
    if result is None:
        raise HTTPException(status_code=400, detail="Result not found")

    try:
        response: dict[str, Any] = {"input_format": "", "input_config": ""}

        inferences = (
            await db_session.execute(
                select(Inference).where(Inference.model_result_id == result_id)
            )
        ).scalars().all()

        if inferences:
            response["input_format"] = inferences[0].input_format
            response["input_config"] = inferences[0].input_config
        else:
            model = result.model
            datasources = (
                await db_session.execute(
                    select(Datasource).where(Datasource.deployment == str(result.deployment_id))
                )
            ).scalars().all()

            if datasources:
                response["input_format"] = datasources[0].input_format
                input_config = datasources[0].input_config

                has_child = (
                    await db_session.execute(
                        select(MLModel.id).where(MLModel.father_id == model.id)
                    )
                ).first() is not None

                if not has_child:
                    response["input_config"] = input_config
                else:
                    data_to_send = {
                        "imports_code": model.imports,
                        "model_code": model.code,
                        "distributed": model.distributed,
                        "request_type": "input_shape",
                    }
                    resp = await http_client.post(
                        settings.TENSORFLOW_EXECUTOR_URL + "exec_tf/", content=json.dumps(data_to_send)
                    )
                    input_shape = resp.content.decode("utf-8")
                    sub = re.search(r", (.+?)\)", input_shape)

                    dictionary = json.loads(input_config)
                    if sub:
                        dictionary["data_reshape"] = sub.group(1).replace(",", "")
                    dictionary["data_type"] = "float32"
                    response["input_config"] = json.dumps(dictionary)

        return response
    except Exception:
        logger.exception("Error resolving inference config for result %s", result_id)
        raise HTTPException(status_code=400, detail="Result not found")




@post("/results/inference/{result_id:int}", tags=["inferences"])
async def deploy_inference(
    result_id: int, data: dict[str, Any], db_session: AsyncSession
) -> None:
    """Expects a JSON body describing a new inference deployment: `replicas`,
    `input_format`, `input_config`, `input_topic`, `output_topic`, `gpumem`,
    and optionally `output_upper`/`token`/`external_host`/the kafka broker
    overrides. Deploys a Kubernetes ReplicationController serving the
    trained model."""
    result = await db_session.get(
        TrainingResult, result_id, options=[selectinload(TrainingResult.model)]
    )
    if result is None:
        raise HTTPException(status_code=400, detail="Result not found")

    try:
        gpu_mem_to_allocate = data.pop("gpumem", 0)

        if result.status != "finished":
            raise HTTPException(status_code=400, detail="Training result is not finished yet")

        inference = Inference(
            model_result=result,
            replicas=data.get("replicas", 1),
            input_format=data.get("input_format", "RAW"),
            input_config=data.get("input_config", ""),
            input_topic=data.get("input_topic", ""),
            output_topic=data.get("output_topic", ""),
            limit=data.get("limit"),
            output_upper=data.get("output_upper", ""),
            token=data.get("token"),
            external_host=data.get("external_host"),
            input_kafka_broker=data.get("input_kafka_broker"),
            output_kafka_broker=data.get("output_kafka_broker"),
            upper_kafka_broker=data.get("upper_kafka_broker"),
        )
        db_session.add(inference)
        await db_session.flush()

        # kubernetes_asyncio.config.load_incluster_config is sync in
        # kubernetes-asyncio==32.0.0 - see deployments.py's create_deployment
        # for the full explanation of this real, found-via-testing bug.
        k8s_config.load_incluster_config()

        if not is_blank(inference.external_host) and not is_blank(inference.token):
            token, external_host = inference.token, inference.external_host
        else:
            token = os.environ.get("KUBE_TOKEN")
            external_host = os.environ.get("KUBE_HOST")

        api_client = kubernetes_api_client(token=token, external_host=external_host)
        async with api_client:
            api_instance = k8s_client.CoreV1Api(api_client)

            input_kafka_broker = inference.input_kafka_broker or settings.BOOTSTRAP_SERVERS
            output_kafka_broker = inference.output_kafka_broker or settings.BOOTSTRAP_SERVERS

            if result.model.framework == "tf":
                image = settings.TENSORFLOW_INFERENCE_MODEL_IMAGE
            else:
                image = settings.PYTORCH_INFERENCE_MODEL_IMAGE

            if not result.model.distributed:
                manifest = _single_inference_manifest(
                    inference, result, image, input_kafka_broker, output_kafka_broker
                )
            else:
                upper_kafka_broker = inference.upper_kafka_broker or settings.BOOTSTRAP_SERVERS
                manifest = _distributed_inference_manifest(
                    inference, result, input_kafka_broker, output_kafka_broker, upper_kafka_broker
                )

            if gpu_mem_to_allocate > 0:
                container = manifest["spec"]["template"]["spec"]["containers"][0]
                container.setdefault("resources", {"limits": {}})
                container["resources"]["limits"]["nvidia.com/gpu"] = gpu_mem_to_allocate
                container["env"].append({"name": "NVIDIA_VISIBLE_DEVICES", "value": "all"})
                manifest["spec"]["template"]["spec"]["runtimeClassName"] = "nvidia"

            await api_instance.create_namespaced_replication_controller(
                body=manifest, namespace=settings.KUBE_NAMESPACE
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=400, detail=str(e)) from e


def _single_inference_manifest(inference, result, image, input_kafka_broker, output_kafka_broker) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "ReplicationController",
        "metadata": {
            "name": f"model-inference-{inference.id}",
            "labels": {"name": f"model-inference-{inference.id}"},
        },
        "spec": {
            "replicas": inference.replicas,
            "selector": {"app": f"inference{inference.id}"},
            "template": {
                "metadata": {"labels": {"app": f"inference{inference.id}"}},
                "spec": {
                    "containers": [
                        {
                            "image": image,
                            "name": "inference",
                            "env": [
                                {"name": "INPUT_BOOTSTRAP_SERVERS", "value": input_kafka_broker},
                                {"name": "OUTPUT_BOOTSTRAP_SERVERS", "value": output_kafka_broker},
                                {
                                    "name": "MODEL_ARCH_URL",
                                    "value": f"{os.environ.get('BACKEND_URL')}/results/{result.id}",
                                },
                                {
                                    "name": "MODEL_URL",
                                    "value": f"{os.environ.get('BACKEND_URL')}/results/model/{result.id}",
                                },
                                {"name": "INPUT_FORMAT", "value": inference.input_format},
                                {"name": "INPUT_CONFIG", "value": inference.input_config},
                                {"name": "INPUT_TOPIC", "value": inference.input_topic},
                                {"name": "OUTPUT_TOPIC", "value": inference.output_topic},
                                {"name": "GROUP_ID", "value": f"inf{result.id}"},
                            ],
                        }
                    ],
                    "imagePullPolicy": "Always",
                },
            },
        },
    }


def _distributed_inference_manifest(
    inference, result, input_kafka_broker, output_kafka_broker, upper_kafka_broker
) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "ReplicationController",
        "metadata": {
            "name": f"model-inference-{inference.id}",
            "labels": {"name": f"model-inference-{inference.id}"},
        },
        "spec": {
            "replicas": inference.replicas,
            "selector": {"app": f"inference{inference.id}"},
            "template": {
                "metadata": {"labels": {"app": f"inference{inference.id}"}},
                "spec": {
                    "containers": [
                        {
                            "image": settings.TENSORFLOW_INFERENCE_MODEL_IMAGE,
                            "name": "inference",
                            "env": [
                                {"name": "INPUT_BOOTSTRAP_SERVERS", "value": input_kafka_broker},
                                {"name": "OUTPUT_BOOTSTRAP_SERVERS", "value": output_kafka_broker},
                                {"name": "UPPER_BOOTSTRAP_SERVERS", "value": upper_kafka_broker},
                                {
                                    "name": "MODEL_URL",
                                    "value": f"{os.environ.get('BACKEND_URL')}/results/model/{result.id}",
                                },
                                {"name": "INPUT_FORMAT", "value": inference.input_format},
                                {"name": "INPUT_CONFIG", "value": inference.input_config},
                                {"name": "INPUT_TOPIC", "value": inference.input_topic},
                                {"name": "OUTPUT_TOPIC", "value": inference.output_topic},
                                {"name": "OUTPUT_UPPER", "value": inference.output_upper},
                                {"name": "GROUP_ID", "value": f"inf{result.id}"},
                                {"name": "LIMIT", "value": str(inference.limit)},
                            ],
                        }
                    ],
                    "imagePullPolicy": "Always",
                },
            },
        },
    }


router = Router(
    path="/",
    route_handlers=[
        list_inferences,
        get_inference,
        stop_inference,
        delete_inference,
        suggest_inference_config,
        deploy_inference,
    ],
)
