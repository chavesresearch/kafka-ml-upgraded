"""Dependency providers for shared, long-lived clients.

Both the HTTP client (for calling the tf/pth mlcode_executor services) and
the Kafka producer are created once at app startup (see ``app/main.py``'s
lifespan) and handed out per-request here, instead of the original Django
code's pattern of opening a brand new ``requests`` connection / new
``confluent_kafka.Producer`` on every single call.
"""

import asyncio

import httpx
from aiokafka import AIOKafkaProducer
from litestar.datastructures import State


class LazyKafkaProducer:
    """Connects on first use instead of at app startup.

    ``confluent_kafka.Producer`` (what the original Django backend used)
    only opens a connection when you actually call ``.produce()``/``.flush()``.
    Calling ``AIOKafkaProducer.start()`` eagerly during the app's lifespan
    would make the whole backend fail to boot if Kafka isn't reachable yet -
    a real risk in Kubernetes, where pod startup order isn't guaranteed.
    This preserves the original's lazy-connect behavior.
    """

    def __init__(self, bootstrap_servers: str | None) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._producer: AIOKafkaProducer | None = None
        self._lock = asyncio.Lock()

    async def send_and_wait(self, topic: str, key: bytes, value: bytes) -> None:
        if self._producer is None:
            async with self._lock:
                if self._producer is None:
                    producer = AIOKafkaProducer(bootstrap_servers=self._bootstrap_servers)
                    await producer.start()
                    self._producer = producer
        await self._producer.send_and_wait(topic, key=key, value=value)

    async def stop(self) -> None:
        if self._producer is not None:
            await self._producer.stop()


async def provide_http_client(state: State) -> httpx.AsyncClient:
    return state.http_client


async def provide_kafka_producer(state: State) -> LazyKafkaProducer:
    return state.kafka_producer
