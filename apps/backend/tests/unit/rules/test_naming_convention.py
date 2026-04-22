from home_curator.policies.schema import (
    NamingConventionPolicy,
    NamingPatternConfig,
    RoomOverride,
)
from home_curator.rules.base import Device, EvaluationContext
from home_curator.rules.naming_convention import compile_naming_convention


def _d(**kw):
    defaults = dict(
        id="d1",
        name="snake_case_name",
        name_by_user=None,
        manufacturer=None,
        model=None,
        area_id=None,
        area_name=None,
        integration=None,
        disabled_by=None,
        entities=[],
    )
    defaults.update(kw)
    return Device(**defaults)


def _ctx(**kw):
    defaults = dict(area_name_to_id={}, area_id_to_name={}, exceptions=set())
    defaults.update(kw)
    return EvaluationContext(**defaults)


def _policy(global_preset="snake_case", rooms=None):
    return NamingConventionPolicy(
        id="nc",
        type="naming_convention",
        enabled=True,
        severity="warning",
        **{
            "global": NamingPatternConfig(preset=global_preset),
        },
        rooms=rooms or [],
    )


def test_global_snake_case_passes():
    rule = compile_naming_convention(_policy("snake_case"))
    assert rule.evaluate(_d(name="living_room_lamp"), _ctx()) is None


def test_global_snake_case_fails_on_camelcase():
    rule = compile_naming_convention(_policy("snake_case"))
    issue = rule.evaluate(_d(name="LivingRoomLamp"), _ctx())
    assert issue is not None
    assert "Convention" in issue.message


def test_kebab_case_preset():
    rule = compile_naming_convention(_policy("kebab-case"))
    assert rule.evaluate(_d(name="hall-lamp"), _ctx()) is None
    assert rule.evaluate(_d(name="hall_lamp"), _ctx()) is not None


def test_room_override_resolved_by_name():
    rooms = [RoomOverride(room="Garage", preset="prefix-type-n")]
    rule = compile_naming_convention(_policy("snake_case", rooms=rooms))
    ctx = _ctx(area_name_to_id={"garage": "garage_xyz"}, area_id_to_name={"garage_xyz": "Garage"})
    # Device in Garage must match prefix-type-n (^[a-z]+_[a-z]+_[0-9]+$)
    assert rule.evaluate(_d(name="garage_light_1", area_id="garage_xyz"), ctx) is None
    assert rule.evaluate(_d(name="random_name", area_id="garage_xyz"), ctx) is not None


def test_room_override_resolved_by_area_id():
    rooms = [RoomOverride(area_id="garage_xyz", preset="kebab-case")]
    rule = compile_naming_convention(_policy("snake_case", rooms=rooms))
    ctx = _ctx()
    assert rule.evaluate(_d(name="hall-lamp", area_id="garage_xyz"), ctx) is None
    assert rule.evaluate(_d(name="hall_lamp", area_id="garage_xyz"), ctx) is not None


def test_exception_suppresses():
    rule = compile_naming_convention(_policy("snake_case"))
    ctx = _ctx(exceptions={("d1", "nc")})
    assert rule.evaluate(_d(name="NotSnake"), ctx) is None


def test_custom_global_pattern():
    pol = NamingConventionPolicy(
        id="nc",
        type="naming_convention",
        enabled=True,
        severity="warning",
        **{"global": NamingPatternConfig(preset="custom", pattern=r"^X_[0-9]+$")},
        rooms=[],
    )
    rule = compile_naming_convention(pol)
    assert rule.evaluate(_d(name="X_42"), _ctx()) is None
    assert rule.evaluate(_d(name="Y_42"), _ctx()) is not None


def test_unresolvable_room_name_falls_back_to_global_with_error_note():
    rooms = [RoomOverride(room="Ghost", preset="prefix-type-n")]
    rule = compile_naming_convention(_policy("snake_case", rooms=rooms))
    ctx = _ctx()
    # No matching area → policy gets marked as degraded, but evaluation still checks global.
    assert rule.evaluate(_d(name="snake_case_ok"), ctx) is None
    # And it records the unresolved room
    assert "Ghost" in (rule.compile_error or "")
