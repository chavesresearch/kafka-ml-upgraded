#!/usr/bin/env bash
set -e
uv run python3 manage.py makemigrations --noinput
uv run python3 manage.py migrate --run-syncdb
exec uv run gunicorn autoweb.wsgi:application --bind 0.0.0.0:8085 --timeout 0
