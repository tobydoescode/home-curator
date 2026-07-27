# Home Curator Addon

Install by adding this repo to Home Assistant:

**Settings → Add-ons → Add-on Store → ⋮ → Repositories → paste URL**.

Then install "Home Curator" and open it from the sidebar. On first start a default `policies.yaml` is created at `/config/home-curator/policies.yaml`. Edit it directly (the UI also edits a subset of the file via Settings → Naming Conventions) to configure:

- naming-convention rules (global + per-room overrides)
- missing-area detection
- reappeared-after-delete detection
- custom CEL expressions

## Ingress

The addon is served through Home Assistant ingress, which puts it beneath a
per-session path prefix (`/api/hassio_ingress/<token>/`) and strips that prefix
before proxying to the addon on port 8099.

That prefix is load-bearing for the UI. Home Assistant passes it in an
`X-Ingress-Path` header, and the backend injects it into `index.html` as
`<base href>` (see `apps/backend/src/home_curator/api/spa.py`). Every asset,
API call, SSE subscription and router path then resolves against it. The
frontend is built with Vite's `base: "./"` so its asset URLs are relative for
that tag to act on.

Two consequences worth knowing:

- Anything in the frontend that emits an absolute path (`/api/...`,
  `/assets/...`) will break under ingress by reaching the Home Assistant host
  instead of the addon. The `e2e` test suite guards against this.
- Ingress is also the addon's **security boundary**. `config.yaml` exposes no
  `ports:`, so Home Assistant's own authentication is the only thing in front
  of an API that can rename and delete devices and entities. Adding a `ports:`
  mapping would expose that API unauthenticated on the LAN.

## Logs

See the addon's logs for rule-engine errors and HA websocket reconnects.
