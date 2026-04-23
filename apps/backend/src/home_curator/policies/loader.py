"""Load and validate `policies.yaml` into a `PoliciesFile`."""
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from ruamel.yaml import YAML, YAMLError

from home_curator.policies.schema import PoliciesFile


# Baseline policies shipped by the addon. Three device + three entity.
# When `policies.yaml` doesn't exist, the whole list is written on first run.
# When it does exist, missing entries (by id) are merged in on load so users
# whose file predates a new baseline addition (e.g. the entity baseline added
# alongside the Entities view) still get the new sections rendered.
#
# Severities / enabled flags chosen to match the spec defaults:
#   Device baseline (all enabled):
#     - naming-convention   snake_case, warning
#     - missing-room        warning
#     - reappeared          info, device scope (default)
#   Entity baseline:
#     - entity-naming-convention  title-case name + snake_case entity_id,
#                                 warning, ENABLED
#     - entity-missing-area       info, DISABLED by default
#     - entity-reappeared         info, entity scope, DISABLED by default
_BASELINE_POLICIES: list[dict[str, Any]] = [
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
]


def _default_policies() -> PoliciesFile:
    """Full baseline `PoliciesFile` used for fresh installs (no file on disk)."""
    return PoliciesFile.model_validate(
        {"version": 1, "policies": _BASELINE_POLICIES}
    )


def _merge_missing_baselines(loaded: PoliciesFile) -> PoliciesFile:
    """Append any baseline policies whose `id` isn't already in `loaded`.

    Called after a successful load of an existing file so that users upgrading
    from an earlier version (before a given baseline existed) see the new
    built-in sections rendered in the UI. Matching is by `id` (not type) so
    users who intentionally renamed a baseline don't get duplicates. Appending
    only — existing policies are never overwritten, preserving the user's
    severity / enabled toggles and any customisations.

    In-memory merge only. The file on disk remains untouched until the user's
    next Save naturally flushes the full draft through `PUT /api/policies`.
    """
    have_ids = {p.id for p in loaded.policies}
    missing = [b for b in _BASELINE_POLICIES if b["id"] not in have_ids]
    if not missing:
        return loaded
    return PoliciesFile.model_validate(
        {
            "version": loaded.version,
            "policies": [
                *(p.model_dump(mode="json", by_alias=True) for p in loaded.policies),
                *missing,
            ],
        }
    )


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

    When an existing file is loaded successfully, any baseline policy whose
    id isn't present gets appended (see `_merge_missing_baselines`).
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
    return LoadResult(file=_merge_missing_baselines(parsed), error=None)
