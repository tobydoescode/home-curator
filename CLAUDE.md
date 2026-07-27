# Home Curator

Home Assistant app that helps keep Home Assistant devices, entities and more clean.

## Working Style

- Read all relevant files first. Never edit blind.
- Understand the full requirement before writing anything. If unclear, ask.
- Be concise. If unsure, say so and do appropriate research. Never guess.
- Fix errors before moving on. Never skip failures.
- Prefer editing over rewriting whole files.
- Simplest working solution. No over-engineering.
- Write tests where applicable first; run them before starting a new feature and as part of validation before declaring done.
- Write documentation for new features and update existing docs when behaviour changes.
- Add Taskfile tasks when they aid local development or repeated operations.
- User instructions always override this file.

## Verification

`task check` runs what CI gates on: ruff, mypy (strict), TypeScript, and the
backend + frontend test suites.

Two further suites are deselected by default, so `task test` does **not** cover
them:

- `task test:e2e` — the built frontend behind a simulated Home Assistant
  ingress. Run after touching anything that emits a URL: the API client, SSE,
  the router, Vite config, or static serving.
- `task test:realha` — the backend against a pinned Home Assistant container.
  Run after touching `ha_client/`. It is the only check on the websocket
  commands Home Assistant does not document.

`task addon:verify` builds the add-on image and asserts it boots, ships no dev
tooling, and keeps ingress-safe asset paths. Real ingress and the Supervisor's
own add-on handling can only be verified in the devcontainer — see
`home-curator/README.md`.

Docs that state behaviour should be checked against the code, not assumed:
several claims in the READMEs described behaviour that never existed.

## Git Workflow

When dispatching subagents that write code, use `isolation: "worktree"` so they work in an isolated git worktree on a feature branch. Copy .env into all new worktrees. Merge to `main` via PR. Renovate pushes directly to `main`, so always `git pull --rebase` before branching.
