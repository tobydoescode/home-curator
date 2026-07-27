# Home Curator Backend

FastAPI service that powers the Home Curator HA addon.

The common workflow is driven by the **root Taskfile** — most users don't need to call any of the commands below directly. See `../../README.md` for `task setup` / `task dev` / `task test`.

## Environment variables

All of these can go in `.env` at the repo root (loaded by the Taskfile) or be exported directly:

- `SUPERVISOR_TOKEN` — used in production. In dev, use `HA_TOKEN` instead.
- `HA_TOKEN` — long-lived access token for dev (create in HA: **Profile → Security → Long-Lived Access Tokens**).
- `HA_URL` — HA base URL. Dev default: `http://localhost:8123`. Prod: `http://supervisor/core`.
- `CONFIG_DIR` — directory containing `policies.yaml`. Defaults to `/config` in prod — the addon's *own* directory via the `addon_config` mapping, not Home Assistant's config — and `./.dev-config/home-curator` in dev.
- `DATA_DIR` — directory for SQLite DB. Defaults to `/data` in prod, `./.dev-data` in dev.

## Automated tests (no HA required)

Uses `FakeHAClient`; nothing external. From the repo root:

```bash
task test:backend               # fast path via Taskfile
```

Or directly:

```bash
cd apps/backend
uv run pytest                   # 434 tests
uv run pytest --cov=home_curator
uv run pytest tests/unit/
uv run pytest tests/integration/
```

## Fake-ingress tests (`tests/e2e/`)

```bash
task test:e2e                   # builds the frontend, then runs both layers
```

Home Assistant serves the addon beneath a per-session path prefix and strips
it before proxying, passing what it stripped in an `X-Ingress-Path` header.
Nothing else in the test suite can catch a breakage there, because everything
else exercises the app at the origin root, where absolute paths happen to
work.

`tests/e2e/conftest.py` reproduces that contract — a Starlette `Mount` in
front of the real app, plus a middleware that sets the header — and serves
the real built `dist/`. Two layers, both needed:

- **HTTP** (`test_ingress_http.py`) — fetches the page, reads the `<base
  href>` it was given, resolves the page's own asset and API URLs against it,
  and checks they are reachable. No browser.
- **Browser** (`test_ingress_browser.py`) — loads the page in Chromium and
  checks the app boots. A wrong `BrowserRouter` basename passes every HTTP
  check and still renders nothing; only this layer catches it. Verified by
  deliberately breaking the basename: the HTTP layer stayed green, the
  browser layer went red.

The suite skips if `apps/frontend/dist` is missing. Note that
`wait_until="networkidle"` never fires here — the SSE stream is long-lived —
so navigation waits on `load` and leans on Playwright's auto-waiting
assertions.

## Real-Home-Assistant tests (`tests/realha/`)

```bash
task test:realha                # needs Docker; ~10s once the image is cached
```

### Why these exist

Home Curator reads and writes the Home Assistant registries. Those live
behind websocket commands — `config/device_registry/list`,
`config/entity_registry/update`, `config/device_registry/remove_config_entry`
and friends — which are **absent from Home Assistant's published API
reference**. They are first-party and are the supported route (HA's REST API
exposes no registry at all, and the only alternative is editing `.storage`
with HA stopped), but there is no written spec to code `ha_client/websocket.py`
against.

So several things in that module are inferences from observed behaviour:
that `created_at` / `modified_at` arrive as unix floats with `0.0` meaning
"unset"; that every entity registry entry carries a `device_id` key; that
unlinking every config entry from a device makes HA delete it. `FakeHAClient`
cannot check any of that — it encodes the same assumptions.

These tests are the missing spec. They boot a pinned Home Assistant
container, populate it with a known registry shape, and drive it through the
real `WebSocketHAClient`.

### How it works

- `fixtures/config/` is mounted at `/config` in the container. It holds a
  minimal `configuration.yaml` — deliberately **not** `default_config:`,
  which would pull in bluetooth/usb/ssdp/zeroconf discovery and turn a
  ~5-second boot into a minute. `config:` is load-bearing: it is the
  integration that registers the registry websocket commands.
- `fixtures/config/custom_components/curator_test/` is a small fixture
  integration that creates deterministic devices, entities and areas
  mirroring the `fake_ha` fixture in `tests/integration/conftest.py`, so the
  same expectations can be asserted against both. It is excluded from ruff,
  mypy and pyright — it imports `homeassistant`, which is not a dependency of
  this project, and it runs inside the container, not in our virtualenv.
- A token is bootstrapped over the onboarding API: `POST
  /api/onboarding/users` returns an auth code, `POST /auth/token` exchanges
  it for a bearer token. A fresh config directory per session is what keeps
  onboarding reachable.

### Conventions

- Every module **must** declare `pytestmark = pytest.mark.realha`. The suite
  is deselected by default via `addopts` so `task test:backend` stays fast
  and hermetic. Marking from a `pytest_collection_modifyitems` hook does not
  work — the hook receives every collected item, not just this package's, and
  runs after `-m` deselection has already happened.
- The container is **session-scoped and shared**. Mutating tests must restore
  what they changed; destructive tests must use a fixture reserved for them
  (`sensor.disposable`, `sensor.disposable_event`, `multi_entry_device`).
  Deleting a fixture another test reads will fail intermittently depending on
  collection order.

### The pinned image

`HA_IMAGE` in `tests/realha/conftest.py` is pinned, and a Renovate custom
manager (see `renovate.json`) raises a PR when a new Home Assistant is
released. A failing bump PR is an early warning that HA changed a command
Home Curator depends on — which is the main ongoing value of this suite.

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
task lint          # ruff + mypy + tsc, from the repo root
task check         # the above plus both test suites
```

Or directly:

```bash
cd apps/backend
uv run ruff check src tests
uv run mypy src                 # strict; enforced in CI
```
