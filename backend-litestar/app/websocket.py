import asyncio
import json
import logging
import uuid

from aiokafka import AIOKafkaConsumer
from litestar import WebSocket, websocket
from litestar.exceptions import WebSocketDisconnect

from app.config import settings

logger = logging.getLogger(__name__)


def _argmax(values: list[float]) -> int:
    return max(range(len(values)), key=lambda i: values[i])


async def _relay_topic(socket: WebSocket, topic: str, is_classification: bool) -> None:
    """One aiokafka consumer per active subscription, streaming straight
    into the websocket - the async-task equivalent of the original
    per-client `KafkaThread`, minus its lifecycle bug (see below)."""
    consumer = AIOKafkaConsumer(
        topic, bootstrap_servers=settings.BOOTSTRAP_SERVERS, group_id=str(uuid.uuid4())
    )
    await consumer.start()
    logger.info("Kafka consumer created for visualization in topic %s", topic)
    try:
        async for message in consumer:
            try:
                if is_classification:
                    values = json.loads(message.value.decode())["values"]
                    await socket.send_text(str(_argmax(values)))
                else:
                    await socket.send_text(message.value.decode())
            except Exception as e:
                logger.error(str(e))
    finally:
        await consumer.stop()


@websocket("/ws/")
async def kafka_visualization_socket(socket: WebSocket) -> None:
    await socket.accept()
    logger.info("Client connected")

    current_task: asyncio.Task | None = None
    try:
        while True:
            message = await socket.receive_json()
            topic = message["topic"]
            is_classification = message["classification"]

            # The original backend only ever tracked one subscription per
            # connection (`self.subscribers[self.channel_name] = thread`), so
            # resubscribing on the same socket without disconnecting first
            # overwrote the dict entry without stopping the old consumer
            # thread - an orphaned Kafka consumer per resubscribe. Cancelling
            # the previous relay task here before starting the new one fixes
            # that leak.
            if current_task is not None and not current_task.done():
                current_task.cancel()

            current_task = asyncio.create_task(_relay_topic(socket, topic, is_classification))
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    finally:
        if current_task is not None and not current_task.done():
            current_task.cancel()
