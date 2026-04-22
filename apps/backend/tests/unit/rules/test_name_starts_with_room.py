from home_curator.policies.schema import NameStartsWithRoomPolicy
from home_curator.rules.base import Device, EvaluationContext
from home_curator.rules.name_starts_with_room import compile_name_starts_with_room


def _d(**kw):
    defaults = dict(
        id="d1",
        name="living_room_lamp",
        name_by_user=None,
        manufacturer=None,
        model=None,
        area_id="living_room",
        area_name="Living Room",
        integration=None,
        disabled_by=None,
        entities=[],
    )
    defaults.update(kw)
    return Device(**defaults)


def _ctx(exc=None):
    return EvaluationContext(area_name_to_id={}, area_id_to_name={}, exceptions=exc or set())


def _policy(**kw):
    return NameStartsWithRoomPolicy.model_validate(
        {
            "id": "nsr",
            "type": "name_starts_with_room",
            "enabled": True,
            "severity": "warning",
            **kw,
        }
    )


def test_passes_when_name_starts_with_room():
    rule = compile_name_starts_with_room(_policy())
    assert rule.evaluate(_d(name="living_room_lamp"), _ctx()) is None


def test_fires_when_name_does_not_start_with_room():
    rule = compile_name_starts_with_room(_policy())
    issue = rule.evaluate(_d(name="lamp"), _ctx())
    assert issue is not None
    assert "Room" in issue.message


def test_separator_is_enforced():
    """`living_room_lamp` matches prefix `living_room_`, but `living_roomlamp` must NOT."""
    rule = compile_name_starts_with_room(_policy())
    assert rule.evaluate(_d(name="living_roomlamp"), _ctx()) is not None


def test_skips_device_without_area():
    rule = compile_name_starts_with_room(_policy())
    assert rule.evaluate(_d(area_id=None, name="whatever"), _ctx()) is None


def test_custom_separator():
    rule = compile_name_starts_with_room(_policy(separator="-"))
    assert rule.evaluate(_d(name="living_room-lamp"), _ctx()) is None
    assert rule.evaluate(_d(name="living_room_lamp"), _ctx()) is not None


def test_source_area_name_defaults_to_space_separator():
    rule = compile_name_starts_with_room(_policy(source="area_name"))
    # area_name = "Living Room", separator defaults to " "
    assert rule.evaluate(_d(name="Living Room Sonos"), _ctx()) is None
    assert rule.evaluate(_d(name="living_room_sonos"), _ctx()) is not None


def test_source_area_name_skips_when_area_name_missing():
    rule = compile_name_starts_with_room(_policy(source="area_name"))
    assert rule.evaluate(_d(area_name=None, name="anything"), _ctx()) is None


def test_uses_name_by_user_when_set():
    """A device renamed in HA (name_by_user) should be evaluated against
    the renamed value, not the integration's raw name."""
    rule = compile_name_starts_with_room(_policy(source="area_name"))
    # Raw name would fail; name_by_user overrides it and passes.
    d = _d(name="stuck_zigbee_device", name_by_user="Living Room Sonos")
    assert rule.evaluate(d, _ctx()) is None


def test_exception_suppresses():
    rule = compile_name_starts_with_room(_policy())
    ctx = _ctx(exc={("d1", "nsr")})
    assert rule.evaluate(_d(name="lamp"), ctx) is None


def test_disabled_rule_does_not_fire():
    rule = compile_name_starts_with_room(_policy(enabled=False))
    assert rule.evaluate(_d(name="lamp"), _ctx()) is None
