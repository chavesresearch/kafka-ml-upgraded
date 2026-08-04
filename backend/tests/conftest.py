"""Shared pytest fixtures for the backend test suite.

Uses Litestar's `TestClient` against a real (temp-file) sqlite database,
per `CLAUDE.md`'s own documented testing approach - not mocked, except for
the one genuinely external call every test would otherwise need a live
tfexecutor/pthexecutor for (`_check_model_code`, see `test_models.py`).

`DATABASE_URL` must be set *before* anything under `app.*` is imported,
since `app.db` creates its async engine at module-import time - conftest.py
is imported by pytest before any test module, so this file's own top-level
code is the right place to do that.
"""

import os
import tempfile
from pathlib import Path

_tmp_dir = tempfile.mkdtemp(prefix="kafka-ml-backend-tests-")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_tmp_dir}/test.db"
os.environ.setdefault("ALLOWED_HOSTS", "testserver,localhost,127.0.0.1")

import pytest
from litestar.testing import TestClient

from app.db import Base, engine


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    """Creates every table once for the whole test session (a temp sqlite
    file, not the real dev db.sqlite3) - see the module docstring for why
    this can't easily be done per-test-function instead."""
    import asyncio

    async def _create():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create())


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app=app) as c:
        yield c
