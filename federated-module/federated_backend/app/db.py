from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """Declarative base shared by every model in ``app.models``."""


engine = create_async_engine(settings.DATABASE_URL, echo=False)

async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def provide_db_session() -> AsyncIterator[AsyncSession]:
    """Litestar dependency: one AsyncSession per request, committed/rolled back for you."""
    async with async_session_maker() as session:
        async with session.begin():
            yield session


async def create_all() -> None:
    """Creates the schema if it doesn't exist yet.

    This service has exactly two small, stable tables and no schema
    history worth tracking - unlike ../../../backend (real Alembic
    migrations, an evolving schema), a plain `create_all()` at startup is
    proportionate here, matching the original Django app's own
    `migrate --run-syncdb` (a schema sync, not a numbered migration
    history - no `migrations/` directory ever existed for this app).
    """
    from app.models import Datasource, ModelSource  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
