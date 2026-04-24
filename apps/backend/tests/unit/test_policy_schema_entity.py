"""Entity-side policy schema tests. Covers the two new types and the
scope-defaulting behaviour on existing types end-to-end."""
import pytest
from pydantic import ValidationError

from home_curator.policies.schema import (
    CustomPolicy,
    EntityMissingAreaPolicy,
    EntityNamingConventionPolicy,
    PoliciesFile,
    ReappearedAfterDeletePolicy,
)

# ---- EntityMissingAreaPolicy ----

def test_entity_missing_area_minimal():
    p = EntityMissingAreaPolicy.model_validate({
        "id": "ma", "type": "entity_missing_area", "severity": "info",
    })
    assert p.require_own_area is False


def test_entity_missing_area_strict():
    p = EntityMissingAreaPolicy.model_validate({
        "id": "ma", "type": "entity_missing_area", "severity": "info",
        "require_own_area": True,
    })
    assert p.require_own_area is True


# ---- EntityNamingConventionPolicy ----

def test_entity_naming_minimal():
    p = EntityNamingConventionPolicy.model_validate({
        "id": "nc", "type": "entity_naming_convention", "severity": "warning",
        "name": {"global": {"preset": "title-case"}},
        "entity_id": {},
    })
    assert p.name.global_.preset == "title-case"
    assert p.entity_id.starts_with_room is False
    assert p.entity_id.rooms == []


def test_entity_naming_with_both_rooms():
    p = EntityNamingConventionPolicy.model_validate({
        "id": "nc", "type": "entity_naming_convention", "severity": "warning",
        "name": {
            "global": {"preset": "title-case"},
            "starts_with_room": True,
            "rooms": [{"area_id": "g", "enabled": True, "preset": "prefix-type-n"}],
        },
        "entity_id": {
            "starts_with_room": True,
            "rooms": [{"area_id": "g", "enabled": False}],
        },
    })
    assert p.name.starts_with_room is True
    assert p.entity_id.starts_with_room is True
    assert p.entity_id.rooms[0].enabled is False


def test_entity_id_preset_rejected_with_hint():
    """entity_id.preset is NOT settable — schema rejects with a hint that
    tells the user to use the name block if they meant the friendly name."""
    with pytest.raises(ValidationError) as ei:
        EntityNamingConventionPolicy.model_validate({
            "id": "nc", "type": "entity_naming_convention", "severity": "warning",
            "name": {"global": {"preset": "title-case"}},
            "entity_id": {"preset": "kebab-case"},
        })
    assert "name" in str(ei.value).lower()


def test_entity_id_room_override_only_allows_enabled():
    """Entity-id room override is opt-out only — preset/pattern are not accepted."""
    with pytest.raises(ValidationError):
        EntityNamingConventionPolicy.model_validate({
            "id": "nc", "type": "entity_naming_convention", "severity": "warning",
            "name": {"global": {"preset": "title-case"}},
            "entity_id": {
                "rooms": [{"area_id": "g", "enabled": False, "preset": "kebab-case"}],
            },
        })


def test_entity_naming_duplicate_room_in_name_rejected():
    with pytest.raises(ValidationError, match="duplicate room override"):
        EntityNamingConventionPolicy.model_validate({
            "id": "nc", "type": "entity_naming_convention", "severity": "warning",
            "name": {
                "global": {"preset": "title-case"},
                "rooms": [
                    {"area_id": "g", "enabled": True, "preset": "title-case"},
                    {"area_id": "g", "enabled": False},
                ],
            },
            "entity_id": {},
        })


def test_entity_naming_duplicate_room_in_entity_id_rejected():
    with pytest.raises(ValidationError, match="duplicate room override"):
        EntityNamingConventionPolicy.model_validate({
            "id": "nc", "type": "entity_naming_convention", "severity": "warning",
            "name": {"global": {"preset": "title-case"}},
            "entity_id": {
                "rooms": [
                    {"area_id": "g", "enabled": True},
                    {"area_id": "g", "enabled": False},
                ],
            },
        })


# ---- CustomPolicy scope default (cross-check from outside the schema file) ----

def test_custom_policy_scope_defaults_to_devices_end_to_end():
    p = CustomPolicy.model_validate({
        "id": "c", "type": "custom", "severity": "info",
        "assert": "true", "message": "m",
    })
    assert p.scope == "devices"


# ---- ReappearedAfterDeletePolicy scope default ----

def test_reappeared_scope_defaults_to_devices():
    p = ReappearedAfterDeletePolicy.model_validate({
        "id": "r", "type": "reappeared_after_delete", "severity": "info",
    })
    assert p.scope == "devices"


# ---- Discriminator union accepts both new types ----

def test_policies_file_accepts_entity_types():
    f = PoliciesFile.model_validate({
        "version": 1,
        "policies": [
            {
                "id": "en", "type": "entity_naming_convention", "severity": "warning",
                "name": {"global": {"preset": "title-case"}},
                "entity_id": {},
            },
            {
                "id": "ema", "type": "entity_missing_area", "severity": "info",
            },
        ],
    })
    names = [type(p).__name__ for p in f.policies]
    assert names == ["EntityNamingConventionPolicy", "EntityMissingAreaPolicy"]
