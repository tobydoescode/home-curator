# Home Curator Backend

FastAPI service that powers the Home Curator HA addon.

## Environment variables

Create `.env` in `apps/backend/` (gitignored) or export:

- `SUPERVISOR_TOKEN` — used in production. In dev, use `HA_TOKEN` instead.
- `HA_TOKEN` — long-lived access token for dev (create in HA: **Profile → Security → Long-Lived Access Tokens**).
- `HA_URL` — HA base URL. Dev default: `http://localhost:8123`. Prod: `http://supervisor/core`.
- `CONFIG_DIR` — directory containing `policies.yaml`. Defaults to `/config/home-curator` in prod, `./.dev-config/home-curator` in dev.
- `DATA_DIR` — directory for SQLite DB. Defaults to `/data` in prod, `./.dev-data` in dev.

## Automated tests (no HA required)

Uses `FakeHAClient`; nothing external.

```bash
cd apps/backend
uv sync --all-extras
uv run pytest                              # 107 tests
uv run pytest --cov=home_curator           # with coverage
uv run pytest tests/unit/                  # unit only
uv run pytest tests/integration/           # integration only
```

## Manual smoke test against a real HA

1. **Get a long-lived token** in HA: Profile → Security → Long-Lived Access Tokens → **Create Token**.

2. **Seed config and data directories** (one-time):

   ```bash
   cd apps/backend
   mkdir -p .dev-config/home-curator .dev-data
   cp tests/fixtures/sample_policies.yaml .dev-config/home-curator/policies.yaml
   ```

3. **Run migrations**:

   ```bash
   uv run alembic upgrade head
   ```

4. **Start the server**, pointed at your HA instance:

   ```bash
   export HA_URL=http://YOUR-HA-IP:8123
   export HA_TOKEN=<paste-long-lived-token>
   uv run uvicorn home_curator.main:app --reload --port 8099
   ```

5. **Exercise the API** (in another terminal):

   ```bash
   curl http://localhost:8099/api/health
   curl http://localhost:8099/api/devices | jq .
   curl http://localhost:8099/api/devices?with_issues=true | jq .
   curl 'http://localhost:8099/api/devices?q=^kitchen_&regex=true' | jq .
   curl http://localhost:8099/api/policies | jq .

   # SSE stream (-N disables buffering). Leave this open; edits in HA should
   # produce a `data: {"kind":"devices_changed"}` line.
   curl -N http://localhost:8099/api/events
   ```

   Interactive OpenAPI UI: <http://localhost:8099/docs>.

6. **Actions (writes to HA — be deliberate)**:

   ```bash
   # Acknowledge an exception
   curl -X POST http://localhost:8099/api/exceptions \
     -H 'Content-Type: application/json' \
     -d '{"device_id":"<id>","policy_id":"missing-room","acknowledged_by":"me"}'

   # Bulk assign a room
   curl -X POST http://localhost:8099/api/actions/assign-room \
     -H 'Content-Type: application/json' \
     -d '{"device_ids":["<id>"],"area_id":"<area-id>"}'

   # Pattern rename — start with dry_run:true to preview
   curl -X POST http://localhost:8099/api/actions/rename-pattern \
     -H 'Content-Type: application/json' \
     -d '{"device_ids":["<id1>","<id2>"],"pattern":"^old_","replacement":"new_","dry_run":true}'
   ```

7. **Hot reload** — edit `.dev-config/home-curator/policies.yaml` while the server runs. Within ~1s `/api/policies` reflects the change. Invalid YAML keeps the last-good rules loaded and surfaces the error under `error`.

## Troubleshooting

- **`assert ha_url is not None` on startup** — `HA_URL` / `HA_TOKEN` not set.
- **WS auth failure** — token expired or wrong; regenerate in HA profile.
- **Migration errors** — `rm -f .dev-data/curator.db && uv run alembic upgrade head`.
- **Stale policies** — the watcher watches `CONFIG_DIR`; make sure you're editing the file it loaded (printed in the logs at startup).

## Dev quick-loop

```
cd apps/backend
uv run uvicorn home_curator.main:app --reload --port 8099
```

Ruff and mypy:

```
uv run ruff check src tests
uv run mypy src
```
