"""Regression tests for app/job_manifest_generator.py's security hardening
(FUTURE.md's exec() sandboxing pass) - every one of the 8 generator
functions must produce a Job manifest whose pod and container both carry
the shared hardened securityContext. This file had zero test coverage
before, so these also serve as basic manifest-shape smoke tests.
"""

from types import SimpleNamespace

from app.job_manifest_generator import (
    _HARDENED_CONTAINER_SECURITY_CONTEXT,
    _HARDENED_POD_SECURITY_CONTEXT,
    distributed_classic_training,
    distributed_federated_incremental_training,
    distributed_federated_training,
    distributed_incremental_training,
    single_classic_training,
    single_federated_incremental_training,
    single_federated_training,
    single_incremental_training,
)


def _result():
    return SimpleNamespace(id=1)


def _deployment(**overrides):
    base = dict(
        id=1,
        batch=32,
        conf_mat_settings=None,
        unsupervised=False,
        unsupervised_rounds=0,
        confidence=0.5,
        agg_rounds=1,
        min_data=1,
        agg_strategy="FedAvg",
        data_restriction="{}",
        blockchain=False,
        stream_timeout=1000,
        indefinite=False,
        monitoring_metric="loss",
        change="down",
        improvement=0.01,
        optimizer="adam",
        learning_rate=0.01,
        loss="mse",
        metrics="accuracy",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _assert_hardened(job_manifest):
    template = job_manifest["spec"]["template"]
    assert template["metadata"]["labels"]["app"] == "kafka-ml-training"
    pod_spec = template["spec"]
    assert pod_spec["securityContext"] == _HARDENED_POD_SECURITY_CONTEXT
    for container in pod_spec["containers"]:
        assert container["securityContext"] == _HARDENED_CONTAINER_SECURITY_CONTEXT


def test_single_classic_training_hardened():
    _assert_hardened(
        single_classic_training(_result(), _deployment(), "img:test", 1, "{}", "{}", SimpleNamespace(BOOTSTRAP_SERVERS="k:9092", CONTROL_TOPIC="t"))
    )


def test_single_federated_training_hardened():
    _assert_hardened(
        single_federated_training(_result(), _deployment(), "img:test", 5, "{}", "{}", SimpleNamespace(BOOTSTRAP_SERVERS="k:9092", MODEL_LOGGER_TOPIC="t"))
    )


def test_single_federated_training_blockchain_still_hardened():
    _assert_hardened(
        single_federated_training(_result(), _deployment(blockchain=True), "img:test", 9, "{}", "{}", SimpleNamespace(BOOTSTRAP_SERVERS="k:9092", MODEL_LOGGER_TOPIC="t"))
    )


def test_single_incremental_training_hardened():
    _assert_hardened(
        single_incremental_training(_result(), _deployment(), "img:test", 2, "{}", "{}", SimpleNamespace(BOOTSTRAP_SERVERS="k:9092", CONTROL_TOPIC="t"))
    )


def test_single_federated_incremental_training_hardened():
    _assert_hardened(
        single_federated_incremental_training(_result(), _deployment(), "img:test", 6, "{}", "{}", SimpleNamespace(BOOTSTRAP_SERVERS="k:9092", CONTROL_TOPIC="t", MODEL_LOGGER_TOPIC="t"))
    )


def test_distributed_classic_training_hardened():
    _assert_hardened(
        distributed_classic_training("1", "[u1]", "[1]", _deployment(), "img:test", 3, "{}", "{}", SimpleNamespace(BOOTSTRAP_SERVERS="k:9092", CONTROL_TOPIC="t"))
    )


def test_distributed_federated_training_hardened():
    _assert_hardened(
        distributed_federated_training("1", "[u1]", "[1]", _deployment(), "img:test", 7, "{}", "{}", SimpleNamespace(BOOTSTRAP_SERVERS="k:9092", CONTROL_TOPIC="t", MODEL_LOGGER_TOPIC="t"))
    )


def test_distributed_incremental_training_hardened():
    _assert_hardened(
        distributed_incremental_training("1", "[u1]", "[1]", _deployment(), "img:test", 4, "{}", "{}", SimpleNamespace(BOOTSTRAP_SERVERS="k:9092", CONTROL_TOPIC="t"))
    )


def test_distributed_federated_incremental_training_hardened():
    _assert_hardened(
        distributed_federated_incremental_training("1", "[u1]", "[1]", _deployment(), "img:test", 8, "{}", "{}", SimpleNamespace(BOOTSTRAP_SERVERS="k:9092", CONTROL_TOPIC="t", MODEL_LOGGER_TOPIC="t"))
    )
