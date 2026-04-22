# Home Curator

Home Assistant addon that helps keep your instance tidy: mass updates, misconfiguration detection, exception tracking.

## Status

Early development. Backend v0.1 lands first; frontend and addon packaging follow.

## Layout

- `apps/backend/` — FastAPI service. [README](apps/backend/README.md)
- `apps/frontend/` — React UI (coming).
- `home-curator/` — HA addon packaging (coming).

## Backend quick-start

```
cd apps/backend
uv sync --all-extras
uv run pytest
uv run uvicorn home_curator.main:app --reload
```

Then `curl http://localhost:8099/api/devices`.
