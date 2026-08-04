"""Unit tests for `app.config._validate_production_safety` (Critical #2 in
FUTURE.md: DEBUG/ALLOWED_HOSTS must not silently fail open in production).

Doesn't touch the real `app.config.settings` singleton (already imported
and validated once at collection time, against whatever env vars this test
run happens to have) - instead calls the pure validation function directly
against small stand-in objects, since it only reads `.ENVIRONMENT`,
`.DEBUG`, and `.ALLOWED_HOSTS`.
"""

from types import SimpleNamespace

import pytest

from app.config import _validate_production_safety


def _settings(environment: str, debug: bool, allowed_hosts: list[str]) -> SimpleNamespace:
    return SimpleNamespace(ENVIRONMENT=environment, DEBUG=debug, ALLOWED_HOSTS=allowed_hosts)


def test_development_allows_insecure_defaults():
    _validate_production_safety(_settings("development", True, ["*"]))


def test_production_with_secure_config_is_allowed():
    _validate_production_safety(_settings("production", False, ["backend"]))


def test_production_with_debug_enabled_raises():
    with pytest.raises(RuntimeError, match="DEBUG is enabled"):
        _validate_production_safety(_settings("production", True, ["backend"]))


def test_production_with_wildcard_allowed_hosts_raises():
    with pytest.raises(RuntimeError, match="ALLOWED_HOSTS"):
        _validate_production_safety(_settings("production", False, ["*"]))


def test_production_with_both_insecure_reports_both():
    with pytest.raises(RuntimeError) as exc_info:
        _validate_production_safety(_settings("production", True, ["*"]))
    assert "DEBUG is enabled" in str(exc_info.value)
    assert "ALLOWED_HOSTS" in str(exc_info.value)
