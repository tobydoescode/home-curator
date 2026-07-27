# Home Curator Addon

Install by adding this repo to Home Assistant:

**Settings → Add-ons → Add-on Store → ⋮ → Repositories → paste URL**.

Then install "Home Curator" and open it from the sidebar.

On first start the addon creates `/config/home-curator/` and writes a default
`policies.yaml` there. Everything is configurable from **Settings** in the UI,
and the same file can be edited by hand — it is reloaded within about a second
of being saved. Invalid content keeps the last-good rules loaded and shows the
error in the UI rather than taking the addon down.

It configures:

- naming conventions for devices and for entities (global + per-room overrides)
- missing-area detection, for devices and entities
- reappeared-after-delete detection
- custom rules written as CEL expressions, scoped to devices or entities

Your edits are never overwritten. Newly-added built-in rules from an addon
update are merged in on load, keeping your `enabled` and `severity` choices.

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

## Testing against a real Supervisor

`task dev` and the `e2e` suite both exercise the app behind a *simulation* of
ingress. That is enough to catch regressions, but it tests our model of ingress
rather than ingress itself. The devcontainer runs a real Supervisor, so the
add-on is installed, built and proxied exactly as it is on a user's system.

Requires Docker and the VS Code Dev Containers extension. It is heavy — a
privileged container running Docker-in-Docker, Supervisor and Home Assistant —
so it is for occasional verification, not the day-to-day loop. Use `task dev`
for that.

From the host, three steps:

```bash
task devcontainer:up          # boots the container (pulls ~2GB the first time)
task devcontainer:start-ha    # starts Supervisor + Home Assistant; a few minutes
task devcontainer:addon       # builds, registers, installs and starts the addon
```

Then open <http://localhost:7123>, complete onboarding, and find **Home Curator
(dev)** in the sidebar. That serves the add-on through the real ingress proxy.

Other tasks: `devcontainer:logs` tails the add-on's log, `devcontainer:down`
removes the container but keeps the Home Assistant instance, and
`devcontainer:clean` removes both. `clean` only deletes volumes attached to
this devcontainer — it deliberately avoids `docker volume prune`.

Inside VS Code the same steps exist as tasks (**Start Home Assistant**,
**Register local add-on**, **Install App**, **Rebuild and Start App**) if you
prefer *Reopen in Container*.

Two things are easy to trip over:

- `devcontainer_bootstrap` runs automatically but only prepares mounts. It does
  **not** start Supervisor — that is `supervisor_run`, which is why
  `start-ha` is a separate step.
- `apps/frontend/src/api/generated.ts` is gitignored and the image build needs
  it. `devcontainer:up` generates it first; if you run the scripts by hand,
  run `task build:frontend` on the host beforehand. This devcontainer has no
  uv or node toolchain.

After changing source: re-run `task devcontainer:addon`, or the **Rebuild and
Start App** task.

> The `mounts` block in `devcontainer.json` is required, not cosmetic.
> Docker-in-Docker cannot run with `/var/lib/docker` on the container's overlay
> filesystem; without those volumes the inner daemon hangs on "Waiting for
> Docker to initialize…" and Supervisor never starts.

### Why the extra script

The Supervisor cannot build this repository's add-on directly, for two reasons:

- `config.yaml` sets `image:`, which Home Assistant reads as "pull from the
  registry" rather than "build from source".
- The Supervisor builds using the **add-on's own directory** as the Docker
  build context, but `home-curator/Dockerfile` does `COPY apps/backend ...` and
  needs the repository root. That is why the release workflow passes
  `context: .` with `file: home-curator/Dockerfile`.

So the script performs the real build itself — real Dockerfile, correct context
— and registers a thin add-on whose Dockerfile is a single `FROM` of the
resulting image. Its `config.yaml` is derived from the real one with `sed`
rather than duplicated, so ingress, mappings, permissions and version cannot
drift; only the slug, name, and the removed `image:` differ.

The repository's own "Home Curator" entry also appears in the local add-on
store, but will fail to install: it points at a published image, and none has
been released. Use the "(dev)" one.

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
