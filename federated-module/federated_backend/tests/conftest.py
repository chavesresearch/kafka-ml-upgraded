"""Shared pytest fixtures for the federated_backend test suite.

Same approach as ../../../backend/tests/conftest.py (Litestar's
`TestClient` against a real temp-file sqlite database, not mocked) - see
that file's own docstring for why `DATABASE_URL` has to be set before
anything under `app.*` is imported.

Unlike backend's own tests (which tolerate accumulated state across the
whole session, see its own test_models.py), these tests assert exact
row counts (matching the original Django suite's `@pytest.mark.django_db`
per-test transaction rollback) - `_clean_tables` gives each test a truly
empty pair of tables.
"""

import os
import tempfile

_tmp_dir = tempfile.mkdtemp(prefix="kafka-ml-federated-backend-tests-")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_tmp_dir}/test.db"
os.environ.setdefault("ALLOWED_HOSTS", "testserver,localhost,127.0.0.1")

import asyncio

import pytest
from litestar.testing import TestClient

from app.db import Base, engine


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    async def _create():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create())


@pytest.fixture(autouse=True)
def _clean_tables():
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models import Datasource, ModelSource

    async def _clean():
        async with AsyncSession(engine) as session:
            async with session.begin():
                for model in (Datasource, ModelSource):
                    await session.execute(model.__table__.delete())

    asyncio.run(_clean())


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app=app) as c:
        yield c
