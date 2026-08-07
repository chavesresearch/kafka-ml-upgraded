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


# -- fakes for kafkaml_client.datasets (RawSink/Kafka), not the REST API --
#
# `kafkaml_client.datasets.send_dataset`/`send_dataframe` build a real
# `kafkaml_datasources.RawSink`, which talks to Kafka (not the REST API
# above) the moment it's constructed. Same broker-free-fake approach as
# `../../datasources/tests/conftest.py` itself uses to test RawSink -
# duplicated here rather than imported, since it's a handful of lines and
# this test suite shouldn't depend on datasources' own tests/ package
# layout.


class FakeKafkaConsumer:
    """Stands in for `kafka.KafkaConsumer` - `KafkaMLSink.__init__` uses
    one only to look up partition offsets (`partitions_for_topic`,
    `end_offsets`), never to actually read messages.

    `end_offsets` counts how many messages the most recently constructed
    `FakeKafkaProducer` has actually `send()`t to each requested topic so
    far - a real broker's offsets would advance the same way as `RawSink`
    publishes data rows. Without this, `end_offsets` returning a constant
    (e.g. always 0) would make `RawSink`'s own before/after offset diff -
    the mechanism `total_msg` in the control message is computed from -
    always report 0 sent messages regardless of how many rows were
    actually sent, silently defeating any test that checks `total_msg`."""

    instances: list["FakeKafkaConsumer"] = []

    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs
        FakeKafkaConsumer.instances.append(self)

    def partitions_for_topic(self, topic):
        return None if topic is None else {0}

    def end_offsets(self, topic_partitions):
        producer = FakeKafkaProducer.instances[-1] if FakeKafkaProducer.instances else None
        return {
            tp: (0 if producer is None else sum(1 for m in producer.sent if m["topic"] == tp.topic))
            for tp in topic_partitions
        }

    def close(self, autocommit=False):
        pass


class FakeKafkaProducer:
    """Stands in for `kafka.KafkaProducer` - records every `send()`
    instead of writing to a real broker, so a test can inspect exactly
    what `RawSink` published (data rows, and the final control message)."""

    instances: list["FakeKafkaProducer"] = []

    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs
        self.sent: list[dict] = []
        FakeKafkaProducer.instances.append(self)

    def send(self, topic, value=None, key=None):
        self.sent.append({"topic": topic, "key": key, "value": value})

    def flush(self):
        pass

    def close(self):
        pass


@pytest.fixture
def patch_kafka(monkeypatch):
    """Patches `kafka.KafkaConsumer`/`kafka.KafkaProducer` everywhere
    `kafkaml_datasources` holds a reference to them, so constructing a
    `RawSink` (via `send_dataset`/`send_dataframe`) needs no real broker.
    Returns the fake classes so a test can inspect `.instances`."""
    import kafkaml_datasources.sink as sink_mod

    FakeKafkaConsumer.instances = []
    FakeKafkaProducer.instances = []

    monkeypatch.setattr(sink_mod, "KafkaConsumer", FakeKafkaConsumer)
    monkeypatch.setattr(sink_mod, "KafkaProducer", FakeKafkaProducer)

    return {"consumer": FakeKafkaConsumer, "producer": FakeKafkaProducer}
