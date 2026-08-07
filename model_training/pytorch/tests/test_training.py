"""Unit tests for training.py's pure/environment-driven helper functions -
select_gpu, load_environment_vars, split_fit_params, split_val_params.
These had zero test coverage before (unlike the tensorflow sibling's
equivalent helpers), despite being straightforward to test in isolation:
none of them touch Kafka, so no real broker is needed - just os.environ/
subprocess mocking.
"""

import json
import subprocess as sp

import pytest

import training


def test_split_fit_params_buckets_by_ignite_signature():
    fn_kwargs_fit = {
        "shuffle": True,
        "num_workers": 2,
        "non_blocking": True,
        "max_epochs": 5,
        "not_a_real_param": "ignored",
    }

    dataloader_kwargs, trainer_kwargs, run_kwargs = training.split_fit_params(fn_kwargs_fit)

    assert dataloader_kwargs == {"shuffle": True, "num_workers": 2}
    assert trainer_kwargs == {"non_blocking": True}
    assert run_kwargs == {"max_epochs": 5}


def test_split_fit_params_empty_input():
    assert training.split_fit_params({}) == ({}, {}, {})


def test_split_val_params_buckets_by_ignite_signature():
    fn_kwargs_val = {
        "batch_sampler": "x",
        "amp_mode": "amp",
        "epoch_length": 10,
        "unknown": 1,
    }

    dataloader_kwargs, validator_kwargs, run_kwargs = training.split_val_params(fn_kwargs_val)

    assert dataloader_kwargs == {"batch_sampler": "x"}
    assert validator_kwargs == {"amp_mode": "amp"}
    assert run_kwargs == {"epoch_length": 10}


def test_split_val_params_empty_input():
    assert training.split_val_params({}) == ({}, {}, {})


def test_load_environment_vars_parses_all_fields(monkeypatch):
    monkeypatch.setenv("BOOTSTRAP_SERVERS", "kafka:9092")
    monkeypatch.setenv("RESULT_URL", "http://backend/results/1")
    monkeypatch.setenv("RESULT_ID", "1")
    monkeypatch.setenv("CONTROL_TOPIC", "control")
    monkeypatch.setenv("DEPLOYMENT_ID", "42")
    monkeypatch.setenv("BATCH", "32")
    # single-quoted, matching how the backend actually serializes these
    # (see training.py's own .replace("'", '"') call) - not valid JSON as-is
    monkeypatch.setenv("KWARGS_FIT", "{'epochs': 5}")
    monkeypatch.setenv("KWARGS_VAL", "{'shuffle': true}")
    monkeypatch.setenv("CONF_MAT_CONFIG", "{'apply': false}")

    result = training.load_environment_vars()

    (
        bootstrap_servers,
        result_url,
        result_id,
        control_topic,
        deployment_id,
        batch,
        kwargs_fit,
        kwargs_val,
        confussion_matrix,
    ) = result

    assert bootstrap_servers == "kafka:9092"
    assert result_url == "http://backend/results/1"
    assert result_id == "1"
    assert control_topic == "control"
    assert deployment_id == 42
    assert isinstance(deployment_id, int)
    assert batch == 32
    assert isinstance(batch, int)
    assert kwargs_fit == {"epochs": 5}
    assert kwargs_val == {"shuffle": True}
    assert confussion_matrix == {"apply": False}


def test_load_environment_vars_missing_deployment_id_raises(monkeypatch):
    # DEPLOYMENT_ID is int(os.environ.get(...)) with no default - a missing
    # var should fail loudly (TypeError from int(None)), not silently
    # produce a wrong deployment id.
    monkeypatch.delenv("DEPLOYMENT_ID", raising=False)
    monkeypatch.setenv("BOOTSTRAP_SERVERS", "kafka:9092")
    monkeypatch.setenv("RESULT_URL", "http://backend/results/1")
    monkeypatch.setenv("RESULT_ID", "1")
    monkeypatch.setenv("CONTROL_TOPIC", "control")
    monkeypatch.setenv("BATCH", "32")
    monkeypatch.setenv("KWARGS_FIT", "{}")
    monkeypatch.setenv("KWARGS_VAL", "{}")
    monkeypatch.setenv("CONF_MAT_CONFIG", "{}")

    with pytest.raises(TypeError):
        training.load_environment_vars()


def test_select_gpu_masks_nothing_when_nvidia_smi_missing(monkeypatch):
    # No GPU / no nvidia-smi binary - select_gpu must not raise, and must
    # leave CUDA_VISIBLE_DEVICES untouched (the except branch just logs).
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)

    def _raise(*args, **kwargs):
        raise FileNotFoundError("nvidia-smi not found")

    monkeypatch.setattr(training.sp, "check_output", _raise)

    training.select_gpu()

    assert "CUDA_VISIBLE_DEVICES" not in __import__("os").environ


def test_select_gpu_picks_highest_free_memory_gpu(monkeypatch):
    # nvidia-smi's real output format: a header line, then one
    # "<free> MiB" line per GPU.
    fake_output = b"memory.free [MiB]\n2048 MiB\n8192 MiB\n"
    monkeypatch.setattr(training.sp, "check_output", lambda *a, **k: fake_output)
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)

    training.select_gpu()

    # two GPUs both above the 1024 MiB threshold -> picks the single
    # highest-free-memory one (index 1, 8192 MiB), matching the
    # len(available_gpus) > 1 branch's own selection logic.
    assert __import__("os").environ["CUDA_VISIBLE_DEVICES"] == "1"


def test_select_gpu_single_gpu_above_threshold(monkeypatch):
    fake_output = b"memory.free [MiB]\n4096 MiB\n"
    monkeypatch.setattr(training.sp, "check_output", lambda *a, **k: fake_output)
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)

    training.select_gpu()

    assert __import__("os").environ["CUDA_VISIBLE_DEVICES"] == "0"
