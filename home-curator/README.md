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

## Releasing

Home Assistant pulls `<image>:<version>` using the `version` field in
`config.yaml`. For a repository addon it reads that file **from the git repo**,
not from the image — so the bump has to be on `main` before the tag is pushed,
or users stay on the old image with no update prompt.

1. Bump `version:` in `config.yaml`.
2. Add a matching `## <version>` heading to `CHANGELOG.md`.
3. Commit both to `main`. The backend test suite fails if the two disagree
   (`tests/unit/test_addon_metadata.py`), so this is checked on every PR.
4. Tag and push: `git tag 0.2.0 && git push origin 0.2.0`.

The release workflow strips a leading `v` if present, so `v0.2.0` and `0.2.0`
both work, and refuses to publish if the tag and `config.yaml` disagree.

## Logs

See the addon's logs for rule-engine errors and HA websocket reconnects.
