"""Write policies.yaml, preserving comments and key order when possible."""
import os
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError


def write_policies_file(path: Path, data: dict[str, Any]) -> None:
    """Write `data` to `path` atomically, creating the directory if needed.

    If the file exists it is loaded in round-trip mode and overwritten in
    place, keeping its top-of-file comments, so user-authored comments in
    git-versioned configs survive UI edits.

    The write goes to a temporary file in the same directory and is then
    renamed over the target. `open("w")` truncates on open, so writing
    directly left the file empty or partial for the duration of the dump: a
    crash there destroyed the user's policies, and the file watcher — which
    watches this very directory — could read the wreckage and report a
    spurious syntax error mid-save. `os.replace` is atomic on POSIX, so a
    reader sees either the old file or the new one. The temporary file must
    live in the same directory to guarantee that: a rename across
    filesystems is not atomic.

    The parent directory is created rather than required. Under the addon it
    is `/config/home-curator`, which does not exist on a fresh install — and
    nothing else creates it, so refusing here meant the very first policy
    save failed. Owning the invariant in the writer also means it holds no
    matter which `Settings` instance produced `path`.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 120

    payload = _merge_into_existing(yaml, path, data)

    tmp = path.with_name(f".{path.name}.tmp")
    try:
        with tmp.open("w") as f:
            yaml.dump(payload, f)
            # Flush through to disk before the rename, so a power loss cannot
            # leave the rename visible while the contents are not.
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _merge_into_existing(yaml: YAML, path: Path, data: dict[str, Any]) -> Any:
    """Return `data` laid over the file's current contents, comments intact.

    Falls back to `data` alone when there is nothing to merge into. That
    includes the case where the existing file does not parse: comment
    preservation is best-effort, and the caller is explicitly replacing the
    contents anyway. Propagating the parse error instead meant a file left
    corrupt by an interrupted write failed *every* subsequent save with an
    unhandled 500, so the UI could not repair the damage it had caused.
    """
    if not path.exists():
        return data
    try:
        existing = yaml.load(path.read_text())
    except (YAMLError, OSError, UnicodeDecodeError):
        return data
    if existing is None:
        return data

    for key in list(existing.keys()):
        if key not in data:
            del existing[key]
    for key, value in data.items():
        existing[key] = value
    return existing
