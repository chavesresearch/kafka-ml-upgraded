"""Unit tests for utils.py's download_model - had zero test coverage
before. Mocks requests.get (no real backend/HTTP needed) to cover the
success path (real exec() of downloaded source, matching the model-code
contract documented in CLAUDE.md) and the retries-exhausted path.
"""

from types import SimpleNamespace

import utils


class _FakeResponse:
    def __init__(self, text: str):
        self.content = text.encode("utf-8")


def test_download_model_execs_source_and_returns_model(monkeypatch):
    # Mirrors the real wire contract (CLAUDE.md's "Model code contract"):
    # the backend returns raw Python source text that must define a
    # `model` name in the exec'd globals.
    source = "model = 'a real model object'"
    monkeypatch.setattr(utils.requests, "get", lambda *a, **k: _FakeResponse(source))

    result = utils.download_model("http://backend/results/1", retries=3, sleep_time=0)

    assert result == "a real model object"


def test_download_model_retries_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def _flaky_get(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("backend not ready yet")
        return _FakeResponse("model = 42")

    monkeypatch.setattr(utils.requests, "get", _flaky_get)
    monkeypatch.setattr(utils.time, "sleep", lambda *_: None)

    result = utils.download_model("http://backend/results/1", retries=5, sleep_time=0)

    assert result == 42
    assert calls["n"] == 3


def test_download_model_returns_none_when_retries_exhausted(monkeypatch):
    monkeypatch.setattr(
        utils.requests,
        "get",
        lambda *a, **k: (_ for _ in ()).throw(ConnectionError("backend unreachable")),
    )
    monkeypatch.setattr(utils.time, "sleep", lambda *_: None)

    result = utils.download_model("http://backend/results/1", retries=3, sleep_time=0)

    assert result is None
