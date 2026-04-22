#!/usr/bin/with-contenv bashio
set -e

export PYTHONPATH=/app/src

cd /app
uv run alembic upgrade head
exec uv run uvicorn home_curator.main:app --host 0.0.0.0 --port 8099
