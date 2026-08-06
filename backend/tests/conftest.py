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

from app.db import Base

# `Base.metadata` only knows about a table once the model class that
# defines it (app/models.py) has actually been imported somewhere - class
# bodies register themselves onto Base.metadata as an import-time side
# effect, there's no other mechanism. Real, deterministic (not flaky - it
# only *looked* timing-dependent while its cause was still a guess) bug
# found running a subset of this suite: pytest always fully *collects*
# (imports) every selected test module before running any of them, so
# `Base.metadata` happened to already be populated by the time
# `_create_schema` below ran, but only because *some* collected file
# imported `app.models` (directly, or transitively via `app.main`) early
# enough - e.g. test_training_results.py does `from app.models import
# ...` at module level. `test_configurations.py`/`test_deployments.py`
# never import model classes directly (they only ever go through the REST
# API), so a selection of just those - or a single one of them - collected
# `Base.metadata` still empty, `create_all` silently created zero tables,
# and every DB-touching call then failed with `sqlite3.OperationalError:
# no such table`. Importing `app.models` explicitly here guarantees the
# metadata is always fully populated before schema creation, regardless of
# which test files happen to be selected.
import app.models  # noqa: F401


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    """Creates every table once for the whole test session (a temp sqlite
    file, not the real dev db.sqlite3) - see the module docstring for why
    this can't easily be done per-test-function instead. A plain
    synchronous engine avoids any complication from sharing `app.db.engine`
    (the async engine real requests use) across event loops - this way
    schema creation is a single blocking call, no coroutine involved."""
    from sqlalchemy import create_engine

    sync_engine = create_engine(f"sqlite:///{_tmp_dir}/test.db")
    Base.metadata.create_all(bind=sync_engine)
    sync_engine.dispose()


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app=app) as c:
        yield c
