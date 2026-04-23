"""Load and validate `policies.yaml` into a `PoliciesFile`."""
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError
from ruamel.yaml import YAML, YAMLError

from home_curator.policies.schema import PoliciesFile


def _default_policies() -> PoliciesFile:
    """Sensible starting state when no policies.yaml exists yet.

    Ships six built-in rules so both the Device and Entity settings pages
    have something to render on first run. Severities / enabled flags
    chosen to match the spec defaults.

    Device baseline (all enabled):
      - naming-convention   snake_case, warning
      - missing-room        warning
      - reappeared          info, device scope (default)

    Entity baseline:
      - entity-naming-convention  title-case name + snake_case entity_id,
                                  warning, ENABLED
      - entity-missing-area       info, DISABLED by default
      - entity-reappeared         info, entity scope, DISABLED by default
    """
    return PoliciesFile.model_validate({
        "version": 1,
        "policies": [
            {
                "id": "naming-convention",
                "type": "naming_convention",
                "enabled": True,
                "severity": "warning",
                "global": {"preset": "snake_case"},
                "starts_with_room": False,
                "rooms": [],
            },
            {
                "id": "missing-room",
                "type": "missing_area",
                "enabled": True,
                "severity": "warning",
            },
            {
                "id": "reappeared",
                "type": "reappeared_after_delete",
                "enabled": True,
                "severity": "info",
            },
            # --- entity baseline ---
            {
                "id": "entity-naming-convention",
                "type": "entity_naming_convention",
                "enabled": True,
                "severity": "warning",
                "name": {
                    "global": {"preset": "title-case"},
                    "starts_with_room": False,
                    "rooms": [],
                },
                "entity_id": {
                    "starts_with_room": False,
                    "rooms": [],
                },
            },
            {
                "id": "entity-missing-area",
                "type": "entity_missing_area",
                "enabled": False,
                "severity": "info",
                "require_own_area": False,
            },
            {
                "id": "entity-reappeared",
                "type": "reappeared_after_delete",
                "enabled": False,
                "severity": "info",
                "scope": "entities",
            },
        ],
    })


@dataclass
class LoadResult:
    file: PoliciesFile | None
    error: str | None


def load_policies_file(path: Path) -> LoadResult:
    """Load + validate a policies YAML file.

    Returns a LoadResult where exactly one of (file, error) is populated.
    A fresh YAML parser instance is used per call so that concurrent callers
    (hot-reload + startup) cannot corrupt shared parser state.

    A missing file is treated as an empty policy set rather than an error —
    first-run of the addon must work without a pre-seeded config, and the
    user creates their first policy through the UI which writes the file.
    Invalid on-disk content is still surfaced as an error.
    """
    if not path.exists():
        return LoadResult(file=_default_policies(), error=None)
    yaml = YAML(typ="safe")
    try:
        text = path.read_text()
    except OSError as e:
        return LoadResult(file=None, error=f"cannot read policies file: {e}")
    try:
        raw = yaml.load(text)
    except YAMLError as e:
        return LoadResult(file=None, error=f"YAML syntax error: {e}")
    if raw is None:
        return LoadResult(file=None, error="policies file is empty")
    try:
        parsed = PoliciesFile.model_validate(raw)
    except ValidationError as e:
        return LoadResult(file=None, error=f"schema error: {e}")
    return LoadResult(file=parsed, error=None)
