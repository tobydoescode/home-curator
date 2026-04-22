"""Write policies.yaml, preserving comments and key order when possible."""
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML


def write_policies_file(path: Path, data: dict[str, Any]) -> None:
    """Write `data` to `path`.

    If the file exists, we load it in round-trip mode, overwrite its contents
    while keeping its top-of-file comments, and write back. This keeps
    user-authored comments in git-versioned configs intact across UI edits.
    """
    if not path.parent.exists():
        raise FileNotFoundError(f"parent directory does not exist: {path.parent}")
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
