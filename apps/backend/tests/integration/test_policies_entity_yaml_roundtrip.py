"""Mixed device + entity policies must survive a write → disk → reload cycle
without drift. Guarantees the schema extensions compose with the existing
YAML writer and that the discriminated union resolves both scopes."""
from pathlib import Path

from home_curator.policies.loader import load_policies_file
from home_curator.policies.schema import PoliciesFile
from home_curator.policies.writer import write_policies_file


def _mixed_policies() -> PoliciesFile:
    """Every rule type, both scopes, every meaningful feature used."""
    return PoliciesFile.model_validate({
        "version": 1,
        "policies": [
            # Device side.
            {
                "id": "nc", "type": "naming_convention", "severity": "warning",
                "global": {"preset": "snake_case"}, "starts_with_room": True,
                "rooms": [
                    {"area_id": "mgmt", "enabled": False},
                    {"room": "Garage", "enabled": True, "preset": "prefix-type-n"},
                ],
            },
            {"id": "ma", "type": "missing_area", "severity": "warning"},
            {
                "id": "r-dev", "type": "reappeared_after_delete",
                "severity": "info", "scope": "devices",
            },
            {
                "id": "c-dev", "type": "custom", "severity": "info",
                "scope": "devices", "when": "true",
                "assert": "device.area_id != null", "message": "m",
            },
            # Entity side.
            {
                "id": "en", "type": "entity_naming_convention", "severity": "warning",
                "name": {
                    "global": {"preset": "title-case"},
                    "starts_with_room": True,
                    "rooms": [{"area_id": "g", "enabled": True, "preset": "prefix-type-n"}],
                },
                "entity_id": {
                    "starts_with_room": True,
                    "rooms": [{"area_id": "g", "enabled": False}],
                },
            },
            {
                "id": "ema", "type": "entity_missing_area", "severity": "info",
                "require_own_area": True,
            },
            {
                "id": "r-ent", "type": "reappeared_after_delete",
                "severity": "info", "scope": "entities",
            },
            {
                "id": "c-ent", "type": "custom", "severity": "info",
                "scope": "entities", "when": "true",
                "assert": "entity.area_id != null", "message": "m",
            },
        ],
    })


def test_mixed_policies_yaml_roundtrip(tmp_path: Path):
    original = _mixed_policies()
    path = tmp_path / "policies.yaml"
    write_policies_file(path, original.model_dump(by_alias=True))

    result = load_policies_file(path)
    assert result.error is None
    reloaded = result.file

    assert reloaded is not None
    # Same number, same types, same ids in the same order.
    assert [type(p).__name__ for p in reloaded.policies] == [
        type(p).__name__ for p in original.policies
    ]
    assert [p.id for p in reloaded.policies] == [p.id for p in original.policies]

    # Spot-check entity-specific fields survive.
    by_id = {p.id: p for p in reloaded.policies}
    en = by_id["en"]
    assert en.name.global_.preset == "title-case"
    assert en.name.starts_with_room is True
    assert en.entity_id.starts_with_room is True
    assert en.entity_id.rooms[0].enabled is False

    ema = by_id["ema"]
    assert ema.require_own_area is True

    c_ent = by_id["c-ent"]
    assert c_ent.scope == "entities"


def test_roundtrip_compiles_through_rule_engine(tmp_path: Path):
    """Extra safety: the reloaded file must compile cleanly through
    the scope-aware engine — catches any discriminator regressions."""
    from home_curator.rules.base import EvaluationContext
    from home_curator.rules.engine import RuleEngine

    original = _mixed_policies()
    path = tmp_path / "policies.yaml"
    write_policies_file(path, original.model_dump(by_alias=True))
    reloaded = load_policies_file(path).file
    assert reloaded is not None

    ctx = EvaluationContext(
        area_name_to_id={"garage": "g", "management": "mgmt"},
        area_id_to_name={"g": "Garage", "mgmt": "Management"},
        exceptions=set(),
        devices_by_id={},
    )
    engine = RuleEngine.compile(reloaded, ctx)
    scopes = {r.id: r.scope for r in engine.compiled}
    assert scopes == {
        "nc": "devices", "ma": "devices", "r-dev": "devices", "c-dev": "devices",
        "en": "entities", "ema": "entities", "r-ent": "entities", "c-ent": "entities",
    }
