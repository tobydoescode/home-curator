# Home Curator Backend

FastAPI service that powers the Home Curator HA addon.

## Dev loop

```
cd apps/backend
uv sync --all-extras
uv run pytest
uv run uvicorn home_curator.main:app --reload --port 8099
```

Environment variables (create `.env` or export):
- `SUPERVISOR_TOKEN` — used in production. In dev, use `HA_TOKEN` with a long-lived access token.
- `HA_URL` — base URL of HA (dev only; prod uses `http://supervisor/core`).
- `CONFIG_DIR` — directory containing `policies.yaml`. Defaults to `/config/home-curator` in prod, `./.dev-config/home-curator` in dev.
- `DATA_DIR` — directory for SQLite DB. Defaults to `/data` in prod, `./.dev-data` in dev.
