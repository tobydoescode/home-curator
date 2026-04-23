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
