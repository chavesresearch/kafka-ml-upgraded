import json
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from litestar import Litestar
from litestar.config.cors import CORSConfig
from litestar.di import Provide

from app.clients import provide_http_client
from app.config import settings
from app.controllers import (
    configurations,
    datasources,
    deployments,
    inferences,
    iot_devices,
    models,
    training_results,
)
from app.db import provide_db_session
from app.websocket import kafka_visualization_socket

logger = logging.getLogger(__name__)


def _maybe_create_blockchain_token() -> None:
    if not settings.ENABLE_FEDML_BLOCKCHAIN:
        return

    from app import blockchain

    try:
        token_address, abi = blockchain.create_token(
            token_name=settings.FEDML_BLOCKCHAIN_TOKEN_NAME,
            token_symbol=settings.FEDML_BLOCKCHAIN_TOKEN_SYMBOL,
            rpc_url=settings.FEDML_BLOCKCHAIN_RPC_URL,
            chain_id=settings.FEDML_BLOCKCHAIN_CHAIN_ID,
            solc_version="0.8.6",
            wallet_address=settings.FEDML_BLOCKCHAIN_WALLET_ADDRESS,
            wallet_key=settings.FEDML_BLOCKCHAIN_WALLET_KEY,
        )
        os.environ["FEDML_BLOCKCHAIN_TOKEN_ADDRESS"] = token_address
        os.environ["FEDML_BLOCKCHAIN_ABI"] = json.dumps(abi)
    except Exception as e:
        logger.error(f"Error creating blockchain token. Some parameters may be missing: {e}")
        raise


@asynccontextmanager
async def lifespan(app: Litestar) -> AsyncIterator[None]:
    for directory in (
        settings.MEDIA_ROOT / settings.MODELS_DIR,
        settings.MEDIA_ROOT / settings.TRAINED_MODELS_DIR,
        settings.MEDIA_ROOT / settings.TFLITE_PARSED_MODELS_DIR,
        settings.DEVICES_ROOT,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    _maybe_create_blockchain_token()

    app.state.http_client = httpx.AsyncClient()

    try:
        yield
    finally:
        await app.state.http_client.aclose()


cors_config = CORSConfig(allow_origins=settings.CORS_ALLOWED_ORIGINS)

dependencies = {
    "db_session": Provide(provide_db_session),
    "http_client": Provide(provide_http_client),
}

app = Litestar(
    route_handlers=[
        models.router,
        configurations.router,
        deployments.router,
        training_results.router,
        inferences.router,
        datasources.router,
        iot_devices.router,
        kafka_visualization_socket,
    ],
    dependencies=dependencies,
    cors_config=cors_config,
    lifespan=[lifespan],
    debug=settings.DEBUG,
)
