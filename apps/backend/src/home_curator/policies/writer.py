"""Write policies.yaml, preserving comments and key order when possible."""
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML


def write_policies_file(path: Path, data: dict[str, Any]) -> None:
    """Write `data` to `path`, creating the containing directory if needed.

    If the file exists, we load it in round-trip mode, overwrite its contents
    while keeping its top-of-file comments, and write back. This keeps
    user-authored comments in git-versioned configs intact across UI edits.

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

    if path.exists():
        existing = yaml.load(path.read_text()) or {}
        for key in list(existing.keys()):
            if key not in data:
                del existing[key]
        for key, value in data.items():
            existing[key] = value
        with path.open("w") as f:
            yaml.dump(existing, f)
        return

    with path.open("w") as f:
        yaml.dump(data, f)
