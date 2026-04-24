# Home Curator Backend

FastAPI service that powers the Home Curator HA addon.

The common workflow is driven by the **root Taskfile** — most users don't need to call any of the commands below directly. See `../../README.md` for `task setup` / `task dev` / `task test`.

## Environment variables

All of these can go in `.env` at the repo root (loaded by the Taskfile) or be exported directly:

- `SUPERVISOR_TOKEN` — used in production. In dev, use `HA_TOKEN` instead.
- `HA_TOKEN` — long-lived access token for dev (create in HA: **Profile → Security → Long-Lived Access Tokens**).
- `HA_URL` — HA base URL. Dev default: `http://localhost:8123`. Prod: `http://supervisor/core`.
- `CONFIG_DIR` — directory containing `policies.yaml`. Defaults to `/config/home-curator` in prod, `./.dev-config/home-curator` in dev.
- `DATA_DIR` — directory for SQLite DB. Defaults to `/data` in prod, `./.dev-data` in dev.

## Automated tests (no HA required)

Uses `FakeHAClient`; nothing external. From the repo root:

```bash
task test:backend               # fast path via Taskfile
```

Or directly:

```bash
cd apps/backend
uv run pytest                   # 112 tests
uv run pytest --cov=home_curator
uv run pytest tests/unit/
uv run pytest tests/integration/
```

## Manual smoke test against a real HA

With `HA_URL` / `HA_TOKEN` set in `.env`:

```bash
task setup:backend              # one-time: seed policies.yaml + migrate
task backend                    # start the API on :8099
```

In another terminal:

```bash
curl http://localhost:8099/api/health
curl http://localhost:8099/api/devices | jq .
curl 'http://localhost:8099/api/devices?with_issues=true' | jq .
curl 'http://localhost:8099/api/devices?q=^kitchen_&regex=true' | jq .
curl http://localhost:8099/api/policies | jq .

# SSE stream (-N disables buffering). Edits in HA produce
# `data: {"kind":"devices_changed"}` lines.
curl -N http://localhost:8099/api/events
```

Interactive OpenAPI UI: <http://localhost:8099/docs>.

### Resource actions (writes to HA — be deliberate)

```bash
# Acknowledge an exception
curl -X POST http://localhost:8099/api/exceptions \
  -H 'Content-Type: application/json' \
  -d '{"device_id":"<id>","policy_id":"missing-room","acknowledged_by":"me"}'

# Bulk assign a room
curl -X POST http://localhost:8099/api/devices/assign-room \
  -H 'Content-Type: application/json' \
  -d '{"device_ids":["<id>"],"area_id":"<area-id>"}'

# Pattern rename — use dry_run:true first to preview
curl -X POST http://localhost:8099/api/devices/rename-pattern \
  -H 'Content-Type: application/json' \
  -d '{"device_ids":["<id1>","<id2>"],"pattern":"^old_","replacement":"new_","dry_run":true}'
```

### Hot reload

Edit `apps/backend/.dev-config/home-curator/policies.yaml` while the server runs. Within ~1s `/api/policies` reflects the change. Invalid YAML keeps the last-good rules loaded and surfaces the error under `error`.

## Troubleshooting

- **`assert ha_url is not None` on startup** — `HA_URL` / `HA_TOKEN` not set. Check `.env` at the repo root.
- **WS auth failure** — token expired or wrong; regenerate in HA profile.
- **Migration errors** — `rm -f apps/backend/.dev-data/curator.db && task setup:backend`.
- **Stale policies** — the watcher watches `CONFIG_DIR`; make sure you're editing the file it loaded (printed in the logs at startup).

## Lint + type-check

```bash
cd apps/backend
uv run ruff check src tests
uv run mypy src
```
