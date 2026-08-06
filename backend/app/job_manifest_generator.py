import os
import json
import random
import string


# Training/inference pods exec() user-submitted model code (see FUTURE.md's
# exec() hardening note) - every Job built below runs with these, shared
# read-only across manifests since nothing mutates them after the fact
# (unlike `deployment.blockchain`, which does get appended to per-manifest
# below).
_HARDENED_CONTAINER_SECURITY_CONTEXT = {
    "runAsNonRoot": True,
    "runAsUser": 1000,
    "allowPrivilegeEscalation": False,
    "capabilities": {"drop": ["ALL"]},
}
_HARDENED_POD_SECURITY_CONTEXT = {
    "seccompProfile": {"type": "RuntimeDefault"},
}


### SINGLE TRAINING JOB MANIFEST GENERATORS ###


# Single Classic Training
def single_classic_training(
    result,
    deployment,
    image,
    case,
    kwargs_fit,
    kwargs_val,
    settings,
):
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": "model-training-" + str(result.id)},
        "spec": {
            "ttlSecondsAfterFinished": 10,
            "template": {
                "metadata": {"labels": {"app": "kafka-ml-training"}},
                "spec": {
                    "securityContext": _HARDENED_POD_SECURITY_CONTEXT,
                    "containers": [
                        {
                            "image": image,
                            "name": "training",
                            "securityContext": _HARDENED_CONTAINER_SECURITY_CONTEXT,
                            "env": [
                                {
                                    "name": "BOOTSTRAP_SERVERS",
                                    "value": settings.BOOTSTRAP_SERVERS,
                                },
                                {
                                    "name": "RESULT_URL",
                                    "value": str(os.environ.get("BACKEND_URL"))
                                    + "/results/"
                                    + str(result.id),
                                },
                                {
                                    "name": "RESULT_ID",
                                    "value": str(result.id),
                                },
                                {
                                    "name": "CONTROL_TOPIC",
                                    "value": settings.CONTROL_TOPIC,
                                },
                                {
                                    "name": "DEPLOYMENT_ID",
                                    "value": str(deployment.id),
                                },
                                {
                                    "name": "BATCH",
                                    "value": str(deployment.batch),
                                },
                                {
                                    "name": "KWARGS_FIT",
                                    "value": kwargs_fit,
                                },
                                {
                                    "name": "KWARGS_VAL",
                                    "value": kwargs_val,
                                },
                                {
                                    "name": "CONF_MAT_CONFIG",
                                    "value": json.dumps(deployment.conf_mat_settings),
                                },
                                {
                                    "name": "CASE",
                                    "value": str(case),
                                },
                                # Unsupservised
                                {
                                    "name": "UNSUPERVISED",
                                    "value": str(deployment.unsupervised),
                                },
                                {
                                    "name": "UNSUPERVISED_ROUNDS",
                                    "value": str(deployment.unsupervised_rounds),
                                },
                                {
                                    "name": "CONFIDENCE",
                                    "value": str(deployment.confidence),
                                },
                            ],
                        }
                    ],
                    "imagePullPolicy": "Always",
                    "restartPolicy": "OnFailure",
                }
            },
        },
    }


# Single Federated Training & Blockchain Training
def single_federated_training(
    result, deployment, image, case, kwargs_fit, kwargs_val, settings
):
    federated_string_id = "".join(
        random.choices(string.digits + string.ascii_lowercase, k=8)
    )

    job_manifest = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": "federated-model-training-controller-" + str(result.id)},
        "spec": {
            "ttlSecondsAfterFinished": 10,
            "template": {
                "metadata": {"labels": {"app": "kafka-ml-training"}},
                "spec": {
                    "securityContext": _HARDENED_POD_SECURITY_CONTEXT,
                    "containers": [
                        {
                            "image": image,
                            "name": "training",
                            "securityContext": _HARDENED_CONTAINER_SECURITY_CONTEXT,
                            "env": [
                                {
                                    "name": "BOOTSTRAP_SERVERS",
                                    "value": settings.BOOTSTRAP_SERVERS,
                                },
                                {
                                    "name": "RESULT_URL",
                                    "value": str(os.environ.get("BACKEND_URL"))
                                    + "/results/"
                                    + str(result.id),
                                },
                                {
                                    "name": "RESULT_ID",
                                    "value": str(result.id),
                                },
                                {
                                    "name": "DEPLOYMENT_ID",
                                    "value": str(deployment.id),
                                },
                                {
                                    "name": "BATCH",
                                    "value": str(deployment.batch),
                                },
                                {
                                    "name": "KWARGS_FIT",
                                    "value": kwargs_fit,
                                },
                                {
                                    "name": "KWARGS_VAL",
                                    "value": kwargs_val,
                                },
                                {
                                    "name": "CONF_MAT_CONFIG",
                                    "value": json.dumps(deployment.conf_mat_settings),
                                },
                                {
                                    "name": "CASE",
                                    "value": str(case),
                                },
                                # Unsupservised
                                {
                                    "name": "UNSUPERVISED",
                                    "value": str(deployment.unsupervised),
                                },
                                {
                                    "name": "UNSUPERVISED_ROUNDS",
                                    "value": str(deployment.unsupervised_rounds),
                                },
                                {
                                    "name": "CONFIDENCE",
                                    "value": str(deployment.confidence),
                                },
                                # Federated
                                {
                                    "name": "AGGREGATION_ROUNDS",
                                    "value": str(deployment.agg_rounds),
                                },
                                {
                                    "name": "MIN_DATA",
                                    "value": str(deployment.min_data),
                                },
                                {
                                    "name": "AGG_STRATEGY",
                                    "value": str(deployment.agg_strategy),
                                },
                                {
                                    "name": "DATA_RESTRICTION",
                                    "value": str(deployment.data_restriction),
                                },
                                {
                                    "name": "MODEL_LOGGER_TOPIC",
                                    "value": str(settings.MODEL_LOGGER_TOPIC),
                                },
                                {
                                    "name": "FEDERATED_STRING_ID",
                                    "value": str(federated_string_id),
                                },
                            ],
                        }
                    ],
                    "imagePullPolicy": "Always",
                    "restartPolicy": "OnFailure",
                }
            },
        },
    }

    if deployment.blockchain:
        # Add Blockchain stuff
        job_manifest["metadata"]["name"] = (
            "federated-blockchain-model-training-controller-" + str(result.id)
        )

        # Coger todas las variables necesarias de las variables de entorno
        job_manifest["spec"]["template"]["spec"]["containers"][0]["env"].append(
            {
                "name": "ETH_RPC_URL",
                "value": str(os.environ.get("FEDML_BLOCKCHAIN_RPC_URL")),
            }
        )
        job_manifest["spec"]["template"]["spec"]["containers"][0]["env"].append(
            {
                "name": "ETH_TOKEN_ADDRESS",
                "value": str(os.environ.get("FEDML_BLOCKCHAIN_TOKEN_ADDRESS")),
            }
        )
        job_manifest["spec"]["template"]["spec"]["containers"][0]["env"].append(
            {
                "name": "ETH_TOKEN_ABI",
                "value": str(os.environ.get("FEDML_BLOCKCHAIN_ABI")),
            }
        )
        job_manifest["spec"]["template"]["spec"]["containers"][0]["env"].append(
            {
                "name": "ETH_CHAIN_ID",
                "value": str(os.environ.get("FEDML_BLOCKCHAIN_CHAIN_ID")),
            }
        )
        job_manifest["spec"]["template"]["spec"]["containers"][0]["env"].append(
            {
                "name": "ETH_NETWORK_ID",
                "value": str(os.environ.get("FEDML_BLOCKCHAIN_NETWORK_ID")),
            }
        )
        job_manifest["spec"]["template"]["spec"]["containers"][0]["env"].append(
            {
                "name": "ETH_WALLET_ADDRESS",
                "value": str(os.environ.get("FEDML_BLOCKCHAIN_WALLET_ADDRESS")),
            }
        )
        # A private key, not config - unlike every other ETH_* var above,
        # never copied out of this process's own env as a literal `value`.
        # This pod's own copy already comes from a Secret (see
        # backend-deployment.yaml's FEDML_BLOCKCHAIN_WALLET_KEY), but
        # re-injecting that resolved value as plaintext here would still
        # hand the raw key to whatever model code this Job execs. Point the
        # training pod at the same Secret directly instead - it never
        # passes through this process's memory or gets written into the Job
        # manifest kubectl/etcd stores.
        job_manifest["spec"]["template"]["spec"]["containers"][0]["env"].append(
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
        job_manifest["spec"]["template"]["spec"]["containers"][0]["env"].append(
            {
                "name": "ETH_BLOCKSCOUT_URL",
                "value": str(os.environ.get("FEDML_BLOCKCHAIN_BLOCKSCOUT_URL")),
            }
        )
    return job_manifest


# Single Incremental Training:
def single_incremental_training(
    result,
    deployment,
    image,
    case,
    kwargs_fit,
    kwargs_val,
    settings,
):
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": "incremental-model-training-" + str(result.id)},
        "spec": {
            "ttlSecondsAfterFinished": 10,
            "template": {
                "metadata": {"labels": {"app": "kafka-ml-training"}},
                "spec": {
                    "securityContext": _HARDENED_POD_SECURITY_CONTEXT,
                    "containers": [
                        {
                            "image": image,
                            "name": "training",
                            "securityContext": _HARDENED_CONTAINER_SECURITY_CONTEXT,
                            "env": [
                                {
                                    "name": "BOOTSTRAP_SERVERS",
                                    "value": settings.BOOTSTRAP_SERVERS,
                                },
                                {
                                    "name": "RESULT_URL",
                                    "value": str(os.environ.get("BACKEND_URL"))
                                    + "/results/"
                                    + str(result.id),
                                },
                                {
                                    "name": "RESULT_ID",
                                    "value": str(result.id),
                                },
                                {
                                    "name": "CONTROL_TOPIC",
                                    "value": settings.CONTROL_TOPIC,
                                },
                                {
                                    "name": "DEPLOYMENT_ID",
                                    "value": str(deployment.id),
                                },
                                {
                                    "name": "BATCH",
                                    "value": str(deployment.batch),
                                },
                                {
                                    "name": "KWARGS_FIT",
                                    "value": kwargs_fit,
                                },
                                {
                                    "name": "KWARGS_VAL",
                                    "value": kwargs_val,
                                },
                                {
                                    "name": "CONF_MAT_CONFIG",
                                    "value": json.dumps(deployment.conf_mat_settings),
                                },
                                {
                                    "name": "CASE",
                                    "value": str(case),
                                },
                                # Unsupservised
                                {
                                    "name": "UNSUPERVISED",
                                    "value": str(deployment.unsupervised),
                                },
                                {
                                    "name": "UNSUPERVISED_ROUNDS",
                                    "value": str(deployment.unsupervised_rounds),
                                },
                                {
                                    "name": "CONFIDENCE",
                                    "value": str(deployment.confidence),
                                },
                                # Incremental
                                {
                                    "name": "STREAM_TIMEOUT",
                                    "value": str(deployment.stream_timeout)
                                    if not deployment.indefinite
                                    else str(-1),
                                },
                                {
                                    "name": "MONITORING_METRIC",
                                    "value": deployment.monitoring_metric,
                                },
                                {
                                    "name": "CHANGE",
                                    "value": deployment.change,
                                },
                                {
                                    "name": "IMPROVEMENT",
                                    "value": str(deployment.improvement),
                                },
                            ],
                        }
                    ],
                    "imagePullPolicy": "Always",
                    "restartPolicy": "OnFailure",
                }
            },
        },
    }


# Single Federated Incremental Training:
def single_federated_incremental_training(
    result,
    deployment,
    image,
    case,
    kwargs_fit,
    kwargs_val,
    settings,
):
    # Generate random string of 5 characters
    federated_string_id = "".join(
        random.choices(string.digits + string.ascii_lowercase, k=8)
    )

    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": "federated-incremental-model-training-controller-" + str(result.id)
        },
        "spec": {
            "ttlSecondsAfterFinished": 10,
            "template": {
                "metadata": {"labels": {"app": "kafka-ml-training"}},
                "spec": {
                    "securityContext": _HARDENED_POD_SECURITY_CONTEXT,
                    "containers": [
                        {
                            "image": image,
                            "name": "training",
                            "securityContext": _HARDENED_CONTAINER_SECURITY_CONTEXT,
                            "env": [
                                {
                                    "name": "BOOTSTRAP_SERVERS",
                                    "value": settings.BOOTSTRAP_SERVERS,
                                },
                                {
                                    "name": "RESULT_URL",
                                    "value": str(os.environ.get("BACKEND_URL"))
                                    + "/results/"
                                    + str(result.id),
                                },
                                {
                                    "name": "RESULT_ID",
                                    "value": str(result.id),
                                },
                                {
                                    "name": "CONTROL_TOPIC",
                                    "value": settings.CONTROL_TOPIC,
                                },
                                {
                                    "name": "DEPLOYMENT_ID",
                                    "value": str(deployment.id),
                                },
                                {
                                    "name": "BATCH",
                                    "value": str(deployment.batch),
                                },
                                {
                                    "name": "KWARGS_FIT",
                                    "value": kwargs_fit,
                                },
                                {
                                    "name": "KWARGS_VAL",
                                    "value": kwargs_val,
                                },
                                {
                                    "name": "CONF_MAT_CONFIG",
                                    "value": json.dumps(deployment.conf_mat_settings),
                                },
                                {
                                    "name": "CASE",
                                    "value": str(case),
                                },
                                # Unsupservised
                                {
                                    "name": "UNSUPERVISED",
                                    "value": str(deployment.unsupervised),
                                },
                                {
                                    "name": "UNSUPERVISED_ROUNDS",
                                    "value": str(deployment.unsupervised_rounds),
                                },
                                {
                                    "name": "CONFIDENCE",
                                    "value": str(deployment.confidence),
                                },
                                # Incremental
                                {
                                    "name": "STREAM_TIMEOUT",
                                    "value": str(deployment.stream_timeout)
                                    if not deployment.indefinite
                                    else str(-1),
                                },
                                {
                                    "name": "MONITORING_METRIC",
                                    "value": deployment.monitoring_metric,
                                },
                                {
                                    "name": "CHANGE",
                                    "value": deployment.change,
                                },
                                {
                                    "name": "IMPROVEMENT",
                                    "value": str(deployment.improvement),
                                },
                                # Federated
                                {
                                    "name": "AGGREGATION_ROUNDS",
                                    "value": str(deployment.agg_rounds),
                                },
                                {
                                    "name": "MIN_DATA",
                                    "value": str(deployment.min_data),
                                },
                                {
                                    "name": "AGG_STRATEGY",
                                    "value": str(deployment.agg_strategy),
                                },
                                {
                                    "name": "DATA_RESTRICTION",
                                    "value": str(deployment.data_restriction),
                                },
                                {
                                    "name": "MODEL_LOGGER_TOPIC",
                                    "value": str(settings.MODEL_LOGGER_TOPIC),
                                },
                                {
                                    "name": "FEDERATED_STRING_ID",
                                    "value": str(federated_string_id),
                                },
                            ],
                        }
                    ],
                    "imagePullPolicy": "Always",
                    "restartPolicy": "OnFailure",
                }
            },
        },
    }


### DISTRIBUTED TRAINING JOB MANIFEST GENERATORS ###


# Distributed Classic Training
def distributed_classic_training(
    n,
    result_urls,
    result_ids,
    deployment,
    image,
    case,
    kwargs_fit,
    kwargs_val,
    settings,
):
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": "distributed-model-training" + n},
        "spec": {
            "ttlSecondsAfterFinished": 10,
            "template": {
                "metadata": {"labels": {"app": "kafka-ml-training"}},
                "spec": {
                    "securityContext": _HARDENED_POD_SECURITY_CONTEXT,
                    "containers": [
                        {
                            "image": image,
                            "name": "training",
                            "securityContext": _HARDENED_CONTAINER_SECURITY_CONTEXT,
                            "env": [
                                {
                                    "name": "BOOTSTRAP_SERVERS",
                                    "value": settings.BOOTSTRAP_SERVERS,
                                },
                                {
                                    "name": "RESULT_URL",
                                    "value": str(result_urls),
                                },
                                {
                                    "name": "RESULT_ID",
                                    "value": str(result_ids),
                                },
                                {
                                    "name": "CONTROL_TOPIC",
                                    "value": settings.CONTROL_TOPIC,
                                },
                                {
                                    "name": "DEPLOYMENT_ID",
                                    "value": str(deployment.id),
                                },
                                {
                                    "name": "BATCH",
                                    "value": str(deployment.batch),
                                },
                                {
                                    "name": "KWARGS_FIT",
                                    "value": kwargs_fit,
                                },
                                {
                                    "name": "KWARGS_VAL",
                                    "value": kwargs_val,
                                },
                                {
                                    "name": "CONF_MAT_CONFIG",
                                    "value": json.dumps(deployment.conf_mat_settings),
                                },
                                {
                                    "name": "CASE",
                                    "value": str(case),
                                },
                                # Distributed
                                {
                                    "name": "OPTIMIZER",
                                    "value": deployment.optimizer,
                                },
                                {
                                    "name": "LEARNING_RATE",
                                    "value": str(deployment.learning_rate),
                                },
                                {
                                    "name": "LOSS",
                                    "value": deployment.loss,
                                },
                                {
                                    "name": "METRICS",
                                    "value": deployment.metrics,
                                },
                                # Unsupservised
                                {
                                    "name": "UNSUPERVISED",
                                    "value": str(deployment.unsupervised),
                                },
                                {
                                    "name": "UNSUPERVISED_ROUNDS",
                                    "value": str(deployment.unsupervised_rounds),
                                },
                                {
                                    "name": "CONFIDENCE",
                                    "value": str(deployment.confidence),
                                },
                            ],
                        }
                    ],
                    "imagePullPolicy": "Always",
                    "restartPolicy": "OnFailure",
                }
            },
        },
    }


# Distributed Federated Training
def distributed_federated_training(
    n,
    result_urls,
    result_ids,
    deployment,
    image,
    case,
    kwargs_fit,
    kwargs_val,
    settings,
):
    federated_string_id = "".join(
        random.choices(string.digits + string.ascii_lowercase, k=8)
    )

    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": "federated-distributed-model-training-controller" + n},
        "spec": {
            "ttlSecondsAfterFinished": 10,
            "template": {
                "metadata": {"labels": {"app": "kafka-ml-training"}},
                "spec": {
                    "securityContext": _HARDENED_POD_SECURITY_CONTEXT,
                    "containers": [
                        {
                            "image": image,
                            "name": "training",
                            "securityContext": _HARDENED_CONTAINER_SECURITY_CONTEXT,
                            "env": [
                                {
                                    "name": "BOOTSTRAP_SERVERS",
                                    "value": settings.BOOTSTRAP_SERVERS,
                                },
                                {
                                    "name": "RESULT_URL",
                                    "value": str(result_urls),
                                },
                                {
                                    "name": "RESULT_ID",
                                    "value": str(result_ids),
                                },
                                {
                                    "name": "CONTROL_TOPIC",
                                    "value": settings.CONTROL_TOPIC,
                                },
                                {
                                    "name": "DEPLOYMENT_ID",
                                    "value": str(deployment.id),
                                },
                                {
                                    "name": "BATCH",
                                    "value": str(deployment.batch),
                                },
                                {
                                    "name": "KWARGS_FIT",
                                    "value": kwargs_fit,
                                },
                                {
                                    "name": "KWARGS_VAL",
                                    "value": kwargs_val,
                                },
                                {
                                    "name": "CONF_MAT_CONFIG",
                                    "value": json.dumps(deployment.conf_mat_settings),
                                },
                                {
                                    "name": "CASE",
                                    "value": str(case),
                                },
                                # Distributed
                                {
                                    "name": "OPTIMIZER",
                                    "value": deployment.optimizer,
                                },
                                {
                                    "name": "LEARNING_RATE",
                                    "value": str(deployment.learning_rate),
                                },
                                {
                                    "name": "LOSS",
                                    "value": deployment.loss,
                                },
                                {
                                    "name": "METRICS",
                                    "value": deployment.metrics,
                                },
                                # Unsupservised
                                {
                                    "name": "UNSUPERVISED",
                                    "value": str(deployment.unsupervised),
                                },
                                {
                                    "name": "UNSUPERVISED_ROUNDS",
                                    "value": str(deployment.unsupervised_rounds),
                                },
                                {
                                    "name": "CONFIDENCE",
                                    "value": str(deployment.confidence),
                                },
                                # Federated
                                {
                                    "name": "AGGREGATION_ROUNDS",
                                    "value": str(deployment.agg_rounds),
                                },
                                {
                                    "name": "MIN_DATA",
                                    "value": str(deployment.min_data),
                                },
                                {
                                    "name": "AGG_STRATEGY",
                                    "value": str(deployment.agg_strategy),
                                },
                                {
                                    "name": "DATA_RESTRICTION",
                                    "value": str(deployment.data_restriction),
                                },
                                {
                                    "name": "MODEL_LOGGER_TOPIC",
                                    "value": str(settings.MODEL_LOGGER_TOPIC),
                                },
                                {
                                    "name": "FEDERATED_STRING_ID",
                                    "value": str(federated_string_id),
                                },
                            ],
                        }
                    ],
                    "imagePullPolicy": "Always",
                    "restartPolicy": "OnFailure",
                }
            },
        },
    }


# Distributed Incremental Training
def distributed_incremental_training(
    n,
    result_urls,
    result_ids,
    deployment,
    image,
    case,
    kwargs_fit,
    kwargs_val,
    settings,
):
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": "distributed-incremental-model-training" + n},
        "spec": {
            "ttlSecondsAfterFinished": 10,
            "template": {
                "metadata": {"labels": {"app": "kafka-ml-training"}},
                "spec": {
                    "securityContext": _HARDENED_POD_SECURITY_CONTEXT,
                    "containers": [
                        {
                            "image": image,
                            "name": "training",
                            "securityContext": _HARDENED_CONTAINER_SECURITY_CONTEXT,
                            "env": [
                                {
                                    "name": "BOOTSTRAP_SERVERS",
                                    "value": settings.BOOTSTRAP_SERVERS,
                                },
                                {
                                    "name": "RESULT_URL",
                                    "value": str(result_urls),
                                },
                                {
                                    "name": "RESULT_ID",
                                    "value": str(result_ids),
                                },
                                {
                                    "name": "CONTROL_TOPIC",
                                    "value": settings.CONTROL_TOPIC,
                                },
                                {
                                    "name": "DEPLOYMENT_ID",
                                    "value": str(deployment.id),
                                },
                                {
                                    "name": "BATCH",
                                    "value": str(deployment.batch),
                                },
                                {
                                    "name": "KWARGS_FIT",
                                    "value": kwargs_fit,
                                },
                                {
                                    "name": "KWARGS_VAL",
                                    "value": kwargs_val,
                                },
                                {
                                    "name": "CONF_MAT_CONFIG",
                                    "value": json.dumps(deployment.conf_mat_settings),
                                },
                                {
                                    "name": "CASE",
                                    "value": str(case),
                                },
                                # Distributed
                                {
                                    "name": "OPTIMIZER",
                                    "value": deployment.optimizer,
                                },
                                {
                                    "name": "LEARNING_RATE",
                                    "value": str(deployment.learning_rate),
                                },
                                {
                                    "name": "LOSS",
                                    "value": deployment.loss,
                                },
                                {
                                    "name": "METRICS",
                                    "value": deployment.metrics,
                                },
                                # Unsupservised
                                {
                                    "name": "UNSUPERVISED",
                                    "value": str(deployment.unsupervised),
                                },
                                {
                                    "name": "UNSUPERVISED_ROUNDS",
                                    "value": str(deployment.unsupervised_rounds),
                                },
                                {
                                    "name": "CONFIDENCE",
                                    "value": str(deployment.confidence),
                                },
                                # Incremental
                                {
                                    "name": "STREAM_TIMEOUT",
                                    "value": str(deployment.stream_timeout)
                                    if not deployment.indefinite
                                    else str(-1),
                                },
                                {
                                    "name": "IMPROVEMENT",
                                    "value": str(deployment.improvement),
                                },
                            ],
                        }
                    ],
                    "imagePullPolicy": "Always",
                    "restartPolicy": "OnFailure",
                }
            },
        },
    }


# Distributed Federated Incremental Training
def distributed_federated_incremental_training(
    n,
    result_urls,
    result_ids,
    deployment,
    image,
    case,
    kwargs_fit,
    kwargs_val,
    settings,
):
    federated_string_id = "".join(
        random.choices(string.digits + string.ascii_lowercase, k=8)
    )

    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": "fed-dist-incremental-model-training-controller" + n},
        "spec": {
            "ttlSecondsAfterFinished": 10,
            "template": {
                "metadata": {"labels": {"app": "kafka-ml-training"}},
                "spec": {
                    "securityContext": _HARDENED_POD_SECURITY_CONTEXT,
                    "containers": [
                        {
                            "image": image,
                            "name": "training",
                            "securityContext": _HARDENED_CONTAINER_SECURITY_CONTEXT,
                            "env": [
                                {
                                    "name": "BOOTSTRAP_SERVERS",
                                    "value": settings.BOOTSTRAP_SERVERS,
                                },
                                {
                                    "name": "RESULT_URL",
                                    "value": str(result_urls),
                                },
                                {
                                    "name": "RESULT_ID",
                                    "value": str(result_ids),
                                },
                                {
                                    "name": "CONTROL_TOPIC",
                                    "value": settings.CONTROL_TOPIC,
                                },
                                {
                                    "name": "DEPLOYMENT_ID",
                                    "value": str(deployment.id),
                                },
                                {
                                    "name": "BATCH",
                                    "value": str(deployment.batch),
                                },
                                {
                                    "name": "KWARGS_FIT",
                                    "value": kwargs_fit,
                                },
                                {
                                    "name": "KWARGS_VAL",
                                    "value": kwargs_val,
                                },
                                {
                                    "name": "CONF_MAT_CONFIG",
                                    "value": json.dumps(deployment.conf_mat_settings),
                                },
                                {
                                    "name": "CASE",
                                    "value": str(case),
                                },
                                # Distributed
                                {
                                    "name": "OPTIMIZER",
                                    "value": deployment.optimizer,
                                },
                                {
                                    "name": "LEARNING_RATE",
                                    "value": str(deployment.learning_rate),
                                },
                                {
                                    "name": "LOSS",
                                    "value": deployment.loss,
                                },
                                {
                                    "name": "METRICS",
                                    "value": deployment.metrics,
                                },
                                # Unsupservised
                                {
                                    "name": "UNSUPERVISED",
                                    "value": str(deployment.unsupervised),
                                },
                                {
                                    "name": "UNSUPERVISED_ROUNDS",
                                    "value": str(deployment.unsupervised_rounds),
                                },
                                {
                                    "name": "CONFIDENCE",
                                    "value": str(deployment.confidence),
                                },
                                # Incremental
                                {
                                    "name": "STREAM_TIMEOUT",
                                    "value": str(deployment.stream_timeout)
                                    if not deployment.indefinite
                                    else str(-1),
                                },
                                {
                                    "name": "IMPROVEMENT",
                                    "value": str(deployment.improvement),
                                },
                                # Federated
                                {
                                    "name": "AGGREGATION_ROUNDS",
                                    "value": str(deployment.agg_rounds),
                                },
                                {
                                    "name": "MIN_DATA",
                                    "value": str(deployment.min_data),
                                },
                                {
                                    "name": "AGG_STRATEGY",
                                    "value": str(deployment.agg_strategy),
                                },
                                {
                                    "name": "DATA_RESTRICTION",
                                    "value": str(deployment.data_restriction),
                                },
                                {
                                    "name": "MODEL_LOGGER_TOPIC",
                                    "value": str(settings.MODEL_LOGGER_TOPIC),
                                },
                                {
                                    "name": "FEDERATED_STRING_ID",
                                    "value": str(federated_string_id),
                                },
                            ],
                        }
                    ],
                    "imagePullPolicy": "Always",
                    "restartPolicy": "OnFailure",
                }
            },
        },
    }
