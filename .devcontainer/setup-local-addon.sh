#!/usr/bin/env bash
# Register Home Curator as a locally-built add-on inside the devcontainer.
#
# Two things stop the Supervisor from building this repository's add-on
# directly:
#
#   1. `home-curator/config.yaml` sets `image:`, which Home Assistant reads as
#      "pull from the registry" rather than "build from source".
#   2. The Supervisor builds using the add-on's *own directory* as the Docker
#      build context, but `home-curator/Dockerfile` does `COPY apps/backend
#      ...` — it needs the repository root. That is why the release workflow
#      passes `context: .` with `file: home-curator/Dockerfile`.
#
# So this assembles a self-contained add-on directory: the real Dockerfile at
# its root, with `apps/` and `home-curator/` beside it so the COPY paths
# resolve. The Supervisor then runs the real production build itself, which
# is more faithful than pre-building and pointing at the result — and it has
# to be this way, because the Supervisor builds with `--pull`, so a Dockerfile
# that `FROM`s a local-only tag can never resolve.
#
# Re-run after changing source, then rebuild the add-on.

set -euo pipefail

ADDON_SLUG="home-curator-dev"

# Home Assistant renamed "add-ons" to "apps": the devcontainer:5-apps image
# scans /mnt/supervisor/apps/local, while older images use addons/local.
# Whichever exists is the one the Supervisor is watching.
LOCAL_ADDONS=""
for candidate in /mnt/supervisor/apps/local /mnt/supervisor/addons/local; do
    if [ -d "$candidate" ]; then
        LOCAL_ADDONS="$candidate"
        break
    fi
done
if [ -z "$LOCAL_ADDONS" ]; then
    echo "error: no local add-on directory under /mnt/supervisor." >&2
    echo "Is the Supervisor running? Run the 'Start Home Assistant' task first." >&2
    exit 1
fi
ADDON_DIR="${LOCAL_ADDONS}/${ADDON_SLUG}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_CONFIG="${ROOT}/home-curator/config.yaml"
GENERATED_TS="${ROOT}/apps/frontend/src/api/generated.ts"

if [ ! -f "$SOURCE_CONFIG" ]; then
    echo "error: ${SOURCE_CONFIG} not found — is the repo mounted correctly?" >&2
    exit 1
fi

# The frontend build stage needs this file and it is gitignored, so it has to
# be generated. It needs both uv and node, which this devcontainer image does
# not carry, so it is generated on the host instead.
if [ ! -f "$GENERATED_TS" ]; then
    cat >&2 <<'MSG'
error: apps/frontend/src/api/generated.ts is missing.

It is gitignored and generated from the backend's OpenAPI schema, and the
frontend build stage needs it. Generate it on your host (not in here — this
devcontainer has no uv/node toolchain):

    task build:frontend

then re-run this script.
MSG
    exit 1
fi

echo "==> Assembling build context at ${ADDON_DIR}"
mkdir -p "$ADDON_DIR"

# Mirrors .dockerignore: everything here is rebuilt inside the image, and
# host node_modules/.venv are built for the wrong platform.
rsync -a --delete \
    --exclude 'node_modules' \
    --exclude '.venv' \
    --exclude 'dist' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.pytest_cache' \
    --exclude '.ruff_cache' \
    --exclude '.mypy_cache' \
    --exclude '.dev-data' \
    --exclude '.dev-config' \
    --exclude 'vite.config.js' \
    --exclude 'vite.config.d.ts' \
    --exclude '*.tsbuildinfo' \
    "${ROOT}/apps" "${ROOT}/home-curator" "${ADDON_DIR}/"

# The Supervisor builds `Dockerfile` from the add-on directory root, so the
# real one is placed there. Its COPY paths resolve against the apps/ and
# home-curator/ trees copied above.
cp "${ROOT}/home-curator/Dockerfile" "${ADDON_DIR}/Dockerfile"

# Derived from the real config.yaml rather than duplicated, so ingress,
# mappings, permissions and version cannot drift. Only the identity changes,
# and `image:` is dropped so the Supervisor builds instead of pulling.
sed \
    -e '/^image:/d' \
    -e "s|^slug: .*|slug: ${ADDON_SLUG}|" \
    -e 's|^name: .*|name: Home Curator (dev)|' \
    "$SOURCE_CONFIG" > "${ADDON_DIR}/config.yaml"

echo
echo "Done. Install and start it with:"
echo "    ha apps reload"
echo "    ha apps install local_${ADDON_SLUG}"
echo "    ha apps start   local_${ADDON_SLUG}"
echo
echo "Or from the VS Code tasks: 'Install App' then 'Start App'."
echo "Home Assistant is on http://localhost:7123 — open the add-on from the"
echo "sidebar to exercise the real ingress path."
echo
echo "After changing source: re-run this script, then 'Rebuild and Start App'."
