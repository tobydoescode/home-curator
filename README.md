# Home Curator

Home Assistant addon that helps keep your instance tidy: mass updates, misconfiguration detection, exception tracking.

## Layout

- `apps/backend/` — FastAPI service. [README](apps/backend/README.md)
- `apps/frontend/` — React + Vite UI. [README](apps/frontend/README.md)
- `home-curator/` — HA addon packaging (Dockerfile, config.yaml, run.sh)
- `docs/architecture/` — diagrams: [data model](docs/architecture/data-model.md), [rule engine](docs/architecture/rule-engine.md), [live updates](docs/architecture/live-updates.md), [frontend](docs/architecture/frontend.md)

## Quick-start (Taskfile)

Requires [Task](https://taskfile.dev) (`brew install go-task/tap/go-task`), [uv](https://github.com/astral-sh/uv), and Node 22.

```
cp .env.example .env
# edit .env → set HA_URL + HA_TOKEN

task setup        # install deps, seed policies.yaml, migrate
task dev          # run backend (:8099) + frontend (:5173) together
```

Open <http://localhost:5173>. Ctrl-C stops both.

Other tasks:

- `task test` — run backend + frontend test suites
- `task test:realha` — run the backend against a real Home Assistant container (needs Docker). See [why](apps/backend/README.md#real-home-assistant-tests-testsrealha).
- `task test:e2e` — drive the built frontend behind a fake Home Assistant ingress (builds the frontend, downloads Chromium)
- `task addon:verify` — build the addon Docker image and check it boots, ships no dev tooling, and keeps ingress-safe asset paths
- Real Supervisor + real ingress: see [testing against a real Supervisor](home-curator/README.md#testing-against-a-real-supervisor)
- `task gen-api` — regenerate the typed API client (run with backend up)
- `task typecheck` — TypeScript check
- `task clean` — remove build artifacts
- `task --list` — everything else
