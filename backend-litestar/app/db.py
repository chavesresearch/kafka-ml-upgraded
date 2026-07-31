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
