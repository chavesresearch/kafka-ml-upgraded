"""A tiny in-memory fake of the parts of the Kafka-ML backend REST API
that KafkaMLClient actually calls, wired in via `httpx.MockTransport` -
httpx's own supported way to test client code without a real server (see
https://www.python-httpx.org/advanced/transports/#mock-transports).

`KafkaMLClient.__init__` builds its own `httpx.Client` with no injection
point, so the fixture below constructs a real client normally, then swaps
its private `_http` for one backed by the mock transport - reaching into
that attribute is deliberate here (not a design flaw to work around
quietly): this SDK is explicitly documented as a draft/PoC
(../CLAUDE.md), and adding DI machinery for a single test fixture isn't
worth a public API change yet.

Mimics just enough of the real contract to exercise this client's own
logic (id-lookup-after-create, before/after id diffing, error wrapping,
polling) - not a full backend reimplementation. Status codes match what
backend/CLAUDE.md documents as the real Litestar contract: POST=201,
DELETE=204, except stop_inference which is POST=200 (an action on an
existing resource, not a creation).
"""

import itertools

import httpx
import pytest

from kafkaml_client import KafkaMLClient


class FakeBackend:
    """In-memory state + request router standing in for the real backend."""

    def __init__(self):
        self._next_id = itertools.count(1)
        self.models: list[dict] = []
        self.configurations: list[dict] = []
        self.deployments: list[dict] = []
        self.results: list[dict] = []
        self.inferences: list[dict] = []

    def _new_id(self) -> int:
        return next(self._next_id)

    def handler(self, request: httpx.Request) -> httpx.Response:
        method = request.method
        path = request.url.path
        body = httpx.Response(200)  # placeholder, overwritten below

        if path == "/models/" and method == "POST":
            data = _json(request)
            self.models.append({"id": self._new_id(), **data})
            return httpx.Response(201)
        if path == "/models/" and method == "GET":
            return httpx.Response(200, json=self.models)
        if path.startswith("/models/") and method == "GET":
            model_id = int(path.rsplit("/", 1)[-1])
            row = next((m for m in self.models if m["id"] == model_id), None)
            return httpx.Response(200, json=row) if row else httpx.Response(404, text="not found")
        if path.startswith("/models/") and method == "DELETE":
            model_id = int(path.rsplit("/", 1)[-1])
            self.models = [m for m in self.models if m["id"] != model_id]
            return httpx.Response(204)

        if path == "/configurations/" and method == "POST":
            data = _json(request)
            self.configurations.append({"id": self._new_id(), **data})
            return httpx.Response(201)
        if path == "/configurations/" and method == "GET":
            return httpx.Response(200, json=self.configurations)
        if path.startswith("/configurations/") and method == "GET":
            config_id = int(path.rsplit("/", 1)[-1])
            row = next((c for c in self.configurations if c["id"] == config_id), None)
            return httpx.Response(200, json=row) if row else httpx.Response(404, text="not found")
        if path.startswith("/configurations/") and method == "DELETE":
            config_id = int(path.rsplit("/", 1)[-1])
            self.configurations = [c for c in self.configurations if c["id"] != config_id]
            return httpx.Response(204)

        if path == "/deployments/" and method == "POST":
            data = _json(request)
            self.deployments.append({"id": self._new_id(), **data})
            return httpx.Response(201)
        if path == "/deployments/" and method == "GET":
            return httpx.Response(200, json=self.deployments)
        if path.startswith("/deployments/") and method == "DELETE":
            deployment_id = int(path.rsplit("/", 1)[-1])
            self.deployments = [d for d in self.deployments if d["id"] != deployment_id]
            return httpx.Response(204)

        if path == "/results/" and method == "GET":
            return httpx.Response(200, json=self.results)

        if path.startswith("/results/inference/") and method == "POST":
            data = _json(request)
            self.inferences.append({"id": self._new_id(), **data})
            return httpx.Response(201)
        if path == "/inferences/" and method == "GET":
            return httpx.Response(200, json=self.inferences)
        if path.startswith("/inferences/") and method == "POST":
            return httpx.Response(200)  # stop_inference
        if path.startswith("/inferences/") and method == "DELETE":
            inference_id = int(path.rsplit("/", 1)[-1])
            self.inferences = [i for i in self.inferences if i["id"] != inference_id]
            return httpx.Response(204)

        return httpx.Response(404, text=f"unhandled {method} {path}")


def _json(request: httpx.Request) -> dict:
    import json

    return json.loads(request.content)


@pytest.fixture
def backend():
    return FakeBackend()


@pytest.fixture
def client(backend):
    c = KafkaMLClient(base_url="http://backend")
    c._http = httpx.Client(transport=httpx.MockTransport(backend.handler), base_url="http://backend")
    with c:
        yield c
