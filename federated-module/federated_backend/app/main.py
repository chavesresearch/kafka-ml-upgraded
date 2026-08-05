from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from litestar import Litestar
from litestar.config.cors import CORSConfig
from litestar.di import Provide

from app.config import settings
from app.controllers import router
from app.db import create_all, provide_db_session


@asynccontextmanager
async def lifespan(app: Litestar) -> AsyncIterator[None]:
    await create_all()
    yield


cors_config = CORSConfig(allow_origins=settings.CORS_ALLOWED_ORIGINS)

dependencies = {
    "db_session": Provide(provide_db_session),
}

app = Litestar(
    route_handlers=[router],
    dependencies=dependencies,
    cors_config=cors_config,
    lifespan=[lifespan],
    debug=settings.DEBUG,
)
