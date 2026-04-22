import pytest
from pydantic import ValidationError

from home_curator.policies.schema import NamingConventionPolicy, PoliciesFile, CustomPolicy, RoomOverride


def test_minimal_file():
    f = PoliciesFile.model_validate({"version": 1, "policies": []})
    assert f.version == 1
    assert f.policies == []


def test_naming_convention_with_preset():
    p = NamingConventionPolicy.model_validate(
        {
            "id": "nc",
            "type": "naming_convention",
            "enabled": True,
            "severity": "warning",
            "global": {"preset": "snake_case"},
            "rooms": [],
        }
    )
    assert p.global_.preset == "snake_case"
    assert p.global_.pattern is None


def test_custom_preset_requires_pattern():
    with pytest.raises(ValidationError):
        NamingConventionPolicy.model_validate(
            {
                "id": "nc",
                "type": "naming_convention",
                "enabled": True,
                "severity": "warning",
                "global": {"preset": "custom"},
                "rooms": [],
            }
        )


def test_room_override_requires_room_or_area_id():
    with pytest.raises(ValidationError):
        NamingConventionPolicy.model_validate(
            {
                "id": "nc",
                "type": "naming_convention",
                "enabled": True,
                "severity": "warning",
                "global": {"preset": "snake_case"},
                "rooms": [{"preset": "snake_case"}],
            }
        )


def test_custom_policy():
    p = CustomPolicy.model_validate(
        {
            "id": "c1",
            "type": "custom",
            "enabled": True,
            "severity": "info",
            "scope": "devices",
            "when": 'device.manufacturer == "Aqara"',
            "assert": "device.area_id != null",
            "message": "msg",
        }
    )
    assert p.when_ == 'device.manufacturer == "Aqara"'


def test_non_custom_preset_rejects_pattern():
    with pytest.raises(ValidationError):
        NamingConventionPolicy.model_validate(
            {
                "id": "nc",
                "type": "naming_convention",
                "enabled": True,
                "severity": "warning",
                "global": {"preset": "snake_case", "pattern": "^.*$"},
                "rooms": [],
            }
        )


def test_empty_id_rejected():
    with pytest.raises(ValidationError):
        NamingConventionPolicy.model_validate(
            {
                "id": "",
                "type": "naming_convention",
                "enabled": True,
                "severity": "warning",
                "global": {"preset": "snake_case"},
                "rooms": [],
            }
        )


def test_whitespace_only_custom_pattern_rejected():
    with pytest.raises(ValidationError):
        NamingConventionPolicy.model_validate(
            {
                "id": "nc",
                "type": "naming_convention",
                "enabled": True,
                "severity": "warning",
                "global": {"preset": "custom", "pattern": "   "},
                "rooms": [],
            }
        )


def test_file_with_mixed_policies():
    raw = {
        "version": 1,
        "policies": [
            {"id": "a", "type": "missing_area", "enabled": True, "severity": "warning"},
            {
                "id": "b",
                "type": "naming_convention",
                "enabled": True,
                "severity": "warning",
                "global": {"preset": "snake_case"},
                "rooms": [],
            },
            {
                "id": "c",
                "type": "reappeared_after_delete",
                "enabled": True,
                "severity": "info",
            },
            {
                "id": "d",
                "type": "custom",
                "enabled": True,
                "severity": "info",
                "scope": "devices",
                "when": "true",
                "assert": "device.area_id != null",
                "message": "x",
            },
        ],
    }
    f = PoliciesFile.model_validate(raw)
    types = [type(p).__name__ for p in f.policies]
    assert types == [
        "MissingAreaPolicy",
        "NamingConventionPolicy",
        "ReappearedAfterDeletePolicy",
        "CustomPolicy",
    ]


def test_naming_convention_has_starts_with_room_default_false():
    p = NamingConventionPolicy.model_validate({
        "id": "nc", "type": "naming_convention", "severity": "warning",
        "global": {"preset": "snake_case"}, "rooms": [],
    })
    assert p.starts_with_room is False


def test_room_override_can_be_disabled():
    o = RoomOverride.model_validate({"area_id": "mgmt", "enabled": False})
    assert o.enabled is False
    # Disabled override doesn't require preset/pattern
    assert o.preset is None


def test_room_override_enabled_requires_preset():
    with pytest.raises(ValidationError):
        RoomOverride.model_validate({"area_id": "mgmt", "enabled": True})


def test_custom_policy_requires_scope():
    with pytest.raises(ValidationError):
        CustomPolicy.model_validate({
            "id": "c", "type": "custom", "severity": "info",
            "assert": "true", "message": "m",
        })


def test_custom_policy_scope_devices_ok():
    p = CustomPolicy.model_validate({
        "id": "c", "type": "custom", "severity": "info", "scope": "devices",
        "assert": "true", "message": "m",
    })
    assert p.scope == "devices"


def test_name_starts_with_room_policy_removed():
    with pytest.raises(ValidationError):
        PoliciesFile.model_validate({
            "version": 1,
            "policies": [{
                "id": "r", "type": "name_starts_with_room",
                "severity": "warning", "source": "area_id",
            }],
        })


def test_naming_convention_starts_with_room_true_accepted():
    p = NamingConventionPolicy.model_validate({
        "id": "nc", "type": "naming_convention", "severity": "warning",
        "global": {"preset": "snake_case"}, "starts_with_room": True,
    })
    assert p.starts_with_room is True
