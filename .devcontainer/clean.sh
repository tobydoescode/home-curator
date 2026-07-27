#!/usr/bin/env bash
# Remove the devcontainer and the volumes belonging to it.
#
# Lives in a script rather than inline in the Taskfile because go-task renders
# its commands as Go templates, so Docker's own `--format '{{range .Mounts}}'`
# gets consumed by Task and reaches Docker as an empty format string. The
# container then gets removed while its volumes are silently left behind.
#
# Deliberately not `docker volume prune`, which removes every unused volume on
# the machine rather than just this project's.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cid="$(docker ps -aq --filter "label=devcontainer.local_folder=${ROOT}" | head -1)"
if [ -z "$cid" ]; then
    echo "No devcontainer found for ${ROOT}"
    exit 0
fi

# Read the volume names before removing the container — afterwards they are
# unreachable and would be orphaned.
volumes="$(docker inspect "$cid" \
    --format '{{range .Mounts}}{{if eq .Type "volume"}}{{.Name}} {{end}}{{end}}')"

docker rm -f "$cid" >/dev/null
echo "Removed devcontainer ${cid:0:12}"

for volume in $volumes; do
    if docker volume rm "$volume" >/dev/null 2>&1; then
        echo "Removed volume ${volume:0:12}"
    else
        echo "Could not remove volume ${volume:0:12} (still in use?)" >&2
    fi
done
