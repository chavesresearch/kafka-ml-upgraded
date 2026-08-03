#!/usr/bin/env bash
set -e
exec uv run uvicorn app:app --host 0.0.0.0 --port 8001
