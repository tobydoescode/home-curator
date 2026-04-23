"""First-run seeding: an empty / missing policies.yaml produces a 6-policy
baseline — the 3 pre-existing device policies plus 3 new entity policies."""
from pathlib import Path

from home_curator.policies.loader import load_policies_file


def test_default_policies_seed_contains_device_and_entity_baseline(tmp_path: Path):
    """When path doesn't exist, loader returns the default baseline."""
    result = load_policies_file(tmp_path / "does-not-exist.yaml")
    assert result.error is None
    assert result.file is not None
    by_id = {p.id: p for p in result.file.policies}
    # Device baseline (pre-existing).
    assert "naming-convention" in by_id
    assert "missing-room" in by_id
    assert "reappeared" in by_id
    # Entity baseline (new).
    assert "entity-naming-convention" in by_id
    assert "entity-missing-area" in by_id
    assert "entity-reappeared" in by_id
    # Baseline is 6 policies total.
    assert len(result.file.policies) == 6


def test_entity_naming_convention_seed_defaults():
    """Name: title-case + starts_with_room=False. Entity_id: starts_with_room=False.
    Warning severity, enabled by default."""
    result = load_policies_file(Path("/nope"))
    assert result.file is not None
    p = next(
        pol for pol in result.file.policies if pol.id == "entity-naming-convention"
    )
    assert p.severity == "warning"
    assert p.enabled is True
    assert p.name.global_.preset == "title-case"
    assert p.name.starts_with_room is False
    assert p.entity_id.starts_with_room is False
    assert p.entity_id.rooms == []


def test_entity_missing_area_seed_disabled_info():
    result = load_policies_file(Path("/nope"))
    assert result.file is not None
    p = next(pol for pol in result.file.policies if pol.id == "entity-missing-area")
    assert p.severity == "info"
    assert p.enabled is False
    assert p.require_own_area is False


def test_entity_reappeared_seed_disabled_info():
    result = load_policies_file(Path("/nope"))
    assert result.file is not None
    p = next(pol for pol in result.file.policies if pol.id == "entity-reappeared")
    assert p.severity == "info"
    assert p.enabled is False
    assert p.scope == "entities"


def test_existing_file_gets_missing_entity_baselines_merged_in(tmp_path: Path):
    """A pre-existing policies.yaml that predates the entity baseline (i.e.
    only has the device-side policies) should have the missing entity
    baselines appended on load so the Entity Settings page has something to
    render. File on disk is not modified."""
    path = tmp_path / "policies.yaml"
    path.write_text(
        """
version: 1
policies:
  - id: naming-convention
    type: naming_convention
    enabled: true
    severity: warning
    global: {preset: snake_case}
    starts_with_room: false
    rooms: []
  - id: missing-room
    type: missing_area
    enabled: true
    severity: warning
  - id: reappeared
    type: reappeared_after_delete
    enabled: true
    severity: info
""".strip()
    )
    original_on_disk = path.read_text()

    result = load_policies_file(path)

    assert result.error is None
    assert result.file is not None
    by_id = {p.id: p for p in result.file.policies}
    # Pre-existing device policies preserved.
    assert "naming-convention" in by_id
    assert "missing-room" in by_id
    assert "reappeared" in by_id
    # Entity baselines merged in.
    assert "entity-naming-convention" in by_id
    assert "entity-missing-area" in by_id
    assert "entity-reappeared" in by_id
    assert len(result.file.policies) == 6

    # File on disk is untouched — merge is in-memory only.
    assert path.read_text() == original_on_disk


def test_merge_preserves_user_customisations_on_existing_baselines(
    tmp_path: Path,
):
    """A user who customised (e.g. disabled) a baseline must not have those
    edits overwritten by the baseline merge."""
    path = tmp_path / "policies.yaml"
    path.write_text(
        """
version: 1
policies:
  - id: missing-room
    type: missing_area
    enabled: false          # user disabled this
    severity: info          # user lowered severity
""".strip()
    )

    result = load_policies_file(path)

    assert result.error is None
    assert result.file is not None
    by_id = {p.id: p for p in result.file.policies}
    mr = by_id["missing-room"]
    assert mr.enabled is False
    assert mr.severity == "info"
    # Baselines the user didn't have are merged in.
    assert "entity-naming-convention" in by_id
    assert "naming-convention" in by_id
