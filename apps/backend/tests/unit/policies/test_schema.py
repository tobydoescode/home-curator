import pytest
from pydantic import ValidationError

from home_curator.policies.schema import NamingConventionPolicy, PoliciesFile, CustomPolicy


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
            "when": 'device.manufacturer == "Aqara"',
            "assert": "device.area_id != null",
            "message": "msg",
        }
    )
    assert p.when_ == 'device.manufacturer == "Aqara"'


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
