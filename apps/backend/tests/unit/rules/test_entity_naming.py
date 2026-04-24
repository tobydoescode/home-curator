"""entity_naming_convention — table-driven. Covers:
  - entity_id enforced to snake_case (with symbol-strip on starts_with_room)
  - friendly name preset behaviour
  - per-room name override (preset swap)
  - per-room entity_id opt-out
  - both blocks fire independently for the same entity
"""
from home_curator.policies.schema import EntityNamingConventionPolicy
from home_curator.rules.base import Entity, EvaluationContext
from home_curator.rules.entity_naming import compile_entity_naming


def _e(entity_id="light.kitchen_lamp", name="Kitchen Lamp", **kw):
    defaults = dict(
        entity_id=entity_id, name=name, original_name=None, icon=None,
        domain="light", platform="hue", device_id=None, area_id=None,
        area_name=None, disabled_by=None, hidden_by=None, unique_id=None,
        created_at=None, modified_at=None, state={},
    )
    defaults.update(kw)
    return Entity(**defaults)


def _ctx(**kw):
    defaults = dict(
        area_name_to_id={}, area_id_to_name={}, exceptions=set(), devices_by_id={},
    )
    defaults.update(kw)
    return EvaluationContext(**defaults)


def _policy(name=None, entity_id=None):
    data = {
        "id": "en", "type": "entity_naming_convention", "severity": "warning",
        "name": name or {"global": {"preset": "title-case"}},
        "entity_id": entity_id or {},
    }
    return EntityNamingConventionPolicy.model_validate(data)


# ---- entity_id enforcement ----

def test_entity_id_snake_case_passes():
    rule = compile_entity_naming(_policy())
    assert rule.evaluate(_e(entity_id="light.kitchen_lamp", name="Kitchen Lamp"), _ctx()) is None


def test_entity_id_camel_case_fails():
    rule = compile_entity_naming(_policy())
    issue = rule.evaluate(_e(entity_id="light.kitchenLamp", name="Kitchen Lamp"), _ctx())
    assert issue is not None
    assert "Entity ID" in issue.message


def test_entity_id_kebab_in_object_fails():
    rule = compile_entity_naming(_policy())
    issue = rule.evaluate(_e(entity_id="light.kitchen-lamp", name="Kitchen Lamp"), _ctx())
    assert issue is not None


def test_entity_id_starts_with_room_symbol_strip_apostrophe():
    """'Clara's Bedroom' → 'claras_bedroom'. entity_id must start with the
    stripped prefix."""
    p = _policy(entity_id={"starts_with_room": True})
    ctx = _ctx(area_id_to_name={"cb": "Clara's Bedroom"})
    rule = compile_entity_naming(p, ctx)
    assert rule.evaluate(
        _e(entity_id="light.claras_bedroom_lamp", name="Clara's Bedroom Lamp",
           area_id="cb"), ctx,
    ) is None
    issue = rule.evaluate(
        _e(entity_id="light.clara_s_bedroom_lamp", name="Clara's Bedroom Lamp",
           area_id="cb"), ctx,
    )
    assert issue is not None


def test_entity_id_starts_with_room_symbol_strip_hyphen():
    """'En-Suite' → 'ensuite'."""
    p = _policy(entity_id={"starts_with_room": True})
    ctx = _ctx(area_id_to_name={"es": "En-Suite"})
    rule = compile_entity_naming(p, ctx)
    assert rule.evaluate(
        _e(entity_id="light.ensuite_lamp", name="En-Suite Lamp", area_id="es"), ctx,
    ) is None
    issue = rule.evaluate(
        _e(entity_id="light.en_suite_lamp", name="En-Suite Lamp", area_id="es"), ctx,
    )
    assert issue is not None


# ---- friendly name preset ----

def test_name_title_case_passes():
    rule = compile_entity_naming(_policy(
        name={"global": {"preset": "title-case"}},
    ))
    assert rule.evaluate(_e(entity_id="light.kitchen_lamp", name="Kitchen Lamp"), _ctx()) is None


def test_name_title_case_fails_on_lowercase():
    rule = compile_entity_naming(_policy(
        name={"global": {"preset": "title-case"}},
    ))
    issue = rule.evaluate(_e(entity_id="light.kitchen_lamp", name="kitchen lamp"), _ctx())
    assert issue is not None
    assert "Name" in issue.message


# ---- per-room name override ----

def test_name_per_room_preset_swap():
    """Garage uses prefix-type-n instead of global title-case."""
    rooms = [{"area_id": "g", "enabled": True, "preset": "prefix-type-n"}]
    rule = compile_entity_naming(_policy(
        name={"global": {"preset": "title-case"}, "rooms": rooms},
    ))
    ctx = _ctx(area_id_to_name={"g": "Garage"})
    # Matches prefix-type-n → passes.
    assert rule.evaluate(
        _e(entity_id="light.garage_light_1", name="garage_light_1", area_id="g"), ctx,
    ) is None
    # Fails prefix-type-n in garage.
    issue = rule.evaluate(
        _e(entity_id="light.garage_light_1", name="Random", area_id="g"), ctx,
    )
    assert issue is not None


# ---- per-room entity_id opt-out ----

def test_entity_id_per_room_opt_out():
    """Garage entity_ids aren't enforced at all — opt-out."""
    rooms = [{"area_id": "g", "enabled": False}]
    rule = compile_entity_naming(_policy(
        entity_id={"rooms": rooms},
    ))
    ctx = _ctx(area_id_to_name={"g": "Garage"})
    # Non-snake entity_id passes because Garage opts out (but the name
    # block still evaluates — "Garage Light" is valid title-case → no issue).
    assert rule.evaluate(
        _e(entity_id="light.GarageLight", name="Garage Light", area_id="g"), ctx,
    ) is None
    # But a non-garage entity is still enforced.
    issue = rule.evaluate(
        _e(entity_id="light.KitchenLamp", name="Kitchen Lamp", area_id=None), ctx,
    )
    assert issue is not None


# ---- exception suppression ----

def test_exception_suppresses():
    rule = compile_entity_naming(_policy())
    ctx = _ctx(exceptions={("entity", "light.kitchenLamp", "en")})
    assert rule.evaluate(_e(entity_id="light.kitchenLamp", name="Kitchen Lamp"), ctx) is None


# ---- both blocks independent ----

def test_name_and_entity_id_both_fire_independently():
    """When both blocks fail, we emit issues for both (caller aggregates)."""
    rule = compile_entity_naming(_policy(
        name={"global": {"preset": "title-case"}},
    ))
    # Bad entity_id AND bad name.
    issues = rule.evaluate_all(_e(entity_id="light.BAD", name="bad"), _ctx())
    messages = [i.message for i in issues]
    assert any("Entity ID" in m for m in messages)
    assert any("Name" in m for m in messages)


# ---- disabled policy ----

def test_disabled_rule_does_not_fire():
    p = EntityNamingConventionPolicy.model_validate({
        "id": "en", "type": "entity_naming_convention", "severity": "warning",
        "enabled": False,
        "name": {"global": {"preset": "title-case"}},
        "entity_id": {},
    })
    rule = compile_entity_naming(p)
    assert rule.evaluate(_e(entity_id="light.BAD", name="bad"), _ctx()) is None


# ---- issue target fields ----

def test_issue_target_fields():
    rule = compile_entity_naming(_policy())
    issue = rule.evaluate(_e(entity_id="light.BadName", name="ok"), _ctx())
    assert issue is not None
    assert issue.target_kind == "entity"
    assert issue.target_id == "light.BadName"


# ---------------------------------------------------------------------------
# starts-with-device logic (name + entity_id blocks)
#
# Anchor for owned entities is the DEVICE's display name (transitively
# room-prefixed by the device rule). Fall back to the room prefix only for
# standalone entities. Dedupe: when the device's name itself doesn't start
# with the room, suppress the entity issue — device rule handles it.
# ---------------------------------------------------------------------------
from home_curator.rules.base import Device  # noqa: E402


def _dev(
    id="d1",
    name="Living Room Lamp",
    area_id="lr",
    area_name="Living Room",
):
    return Device(
        id=id, name=name, name_by_user=None,
        manufacturer=None, model=None,
        area_id=area_id, area_name=area_name,
        integration=None, disabled_by=None,
        entities=[],
    )


def _swr_policy():
    """Both blocks have starts_with_room=True."""
    return _policy(
        name={"global": {"preset": "title-case"}, "starts_with_room": True},
        entity_id={"starts_with_room": True},
    )


# ---- name block ----

def test_name_owned_display_starts_with_device_passes():
    rule = compile_entity_naming(_swr_policy())
    ctx = _ctx(
        area_id_to_name={"lr": "Living Room"},
        devices_by_id={"d1": _dev()},
    )
    entity = _e(
        entity_id="light.living_room_lamp_ambient",
        name="Living Room Lamp Ambient",
        device_id="d1", area_id="lr",
    )
    assert rule.evaluate_all(entity, ctx) == []


def test_name_owned_display_not_starting_with_device_emits_device_issue():
    rule = compile_entity_naming(_swr_policy())
    ctx = _ctx(
        area_id_to_name={"lr": "Living Room"},
        devices_by_id={"d1": _dev()},
    )
    entity = _e(
        entity_id="light.living_room_lamp_ambient",
        name="Ambient",  # title-case passes pattern but not prefix
        device_id="d1", area_id="lr",
    )
    messages = [i.message for i in rule.evaluate_all(entity, ctx)]
    assert "Name Doesn't Start With Device" in messages


def test_name_owned_device_itself_wrong_dedupes_entity_issue():
    """Device 'Lounge Lamp' in room 'Living Room' — device rule will fire;
    suppress entity issue to avoid duplicate complaints."""
    rule = compile_entity_naming(_swr_policy())
    ctx = _ctx(
        area_id_to_name={"lr": "Living Room"},
        devices_by_id={"d1": _dev(name="Lounge Lamp")},
    )
    entity = _e(
        entity_id="light.living_room_lamp_ambient",
        name="Ambient",
        device_id="d1", area_id="lr",
    )
    messages = [i.message for i in rule.evaluate_all(entity, ctx)]
    assert "Name Doesn't Start With Device" not in messages
    assert "Name Doesn't Start With Its Room" not in messages


def test_name_standalone_display_starts_with_room_passes():
    rule = compile_entity_naming(_swr_policy())
    ctx = _ctx(
        area_id_to_name={"lr": "Living Room"},
        devices_by_id={},
    )
    entity = _e(
        entity_id="light.living_room_ambient",
        name="Living Room Ambient",
        device_id=None, area_id="lr",
    )
    assert rule.evaluate_all(entity, ctx) == []


def test_name_standalone_display_not_starting_with_room_emits_room_issue():
    rule = compile_entity_naming(_swr_policy())
    ctx = _ctx(
        area_id_to_name={"lr": "Living Room"},
        devices_by_id={},
    )
    entity = _e(
        entity_id="light.living_room_ambient",
        name="Ambient",
        device_id=None, area_id="lr",
    )
    messages = [i.message for i in rule.evaluate_all(entity, ctx)]
    assert "Name Doesn't Start With Its Room" in messages


def test_name_inherited_from_device_passes():
    """name=None and original_name=None → entity inherits device's name.
    Skip the starts_with check; device rule handles the prefix."""
    rule = compile_entity_naming(_swr_policy())
    ctx = _ctx(
        area_id_to_name={"lr": "Living Room"},
        devices_by_id={"d1": _dev()},
    )
    entity = _e(
        entity_id="light.living_room_lamp",
        name=None, original_name=None,
        device_id="d1", area_id="lr",
    )
    assert rule.evaluate_all(entity, ctx) == []


def test_name_entity_no_area_skips_prefix_check():
    rule = compile_entity_naming(_swr_policy())
    ctx = _ctx(devices_by_id={"d1": _dev(area_id=None, area_name=None)})
    entity = _e(
        entity_id="light.living_room_lamp_ambient",
        name="Living Room Lamp Ambient",
        device_id="d1", area_id=None,
    )
    assert rule.evaluate_all(entity, ctx) == []


# ---- entity_id block ----

def test_entity_id_owned_object_starts_with_snake_device_passes():
    rule = compile_entity_naming(_swr_policy())
    ctx = _ctx(
        area_id_to_name={"lr": "Living Room"},
        devices_by_id={"d1": _dev()},
    )
    entity = _e(
        entity_id="light.living_room_lamp_ambient",
        name="Living Room Lamp Ambient",
        device_id="d1", area_id="lr",
    )
    assert rule.evaluate_all(entity, ctx) == []


def test_entity_id_owned_object_not_starting_with_device_emits_device_issue():
    rule = compile_entity_naming(_swr_policy())
    ctx = _ctx(
        area_id_to_name={"lr": "Living Room"},
        devices_by_id={"d1": _dev()},
    )
    entity = _e(
        entity_id="light.ambient",
        name="Living Room Lamp Ambient",
        device_id="d1", area_id="lr",
    )
    messages = [i.message for i in rule.evaluate_all(entity, ctx)]
    assert "Entity ID Doesn't Start With Device" in messages


def test_entity_id_owned_device_snake_wrong_dedupes():
    rule = compile_entity_naming(_swr_policy())
    ctx = _ctx(
        area_id_to_name={"lr": "Living Room"},
        devices_by_id={"d1": _dev(name="Lounge Lamp")},  # snake "lounge_lamp"
    )
    entity = _e(
        entity_id="light.ambient",
        name="Living Room Lamp Ambient",
        device_id="d1", area_id="lr",
    )
    messages = [i.message for i in rule.evaluate_all(entity, ctx)]
    assert "Entity ID Doesn't Start With Device" not in messages
    assert "Entity ID Doesn't Start With Its Room" not in messages


def test_entity_id_standalone_object_starts_with_snake_room_passes():
    rule = compile_entity_naming(_swr_policy())
    ctx = _ctx(
        area_id_to_name={"lr": "Living Room"},
        devices_by_id={},
    )
    entity = _e(
        entity_id="light.living_room_ambient",
        name="Living Room Ambient",
        device_id=None, area_id="lr",
    )
    assert rule.evaluate_all(entity, ctx) == []


def test_entity_id_standalone_object_wrong_emits_room_issue():
    rule = compile_entity_naming(_swr_policy())
    ctx = _ctx(
        area_id_to_name={"lr": "Living Room"},
        devices_by_id={},
    )
    entity = _e(
        entity_id="light.ambient",
        name="Living Room Ambient",
        device_id=None, area_id="lr",
    )
    messages = [i.message for i in rule.evaluate_all(entity, ctx)]
    assert "Entity ID Doesn't Start With Its Room" in messages


def test_entity_id_exactly_matches_snake_device_passes():
    """HA's default entity_id (object_id == snake(device)) is treated as
    inherited — no custom suffix, so 'starts_with_device' is satisfied."""
    rule = compile_entity_naming(_swr_policy())
    ctx = _ctx(
        area_id_to_name={"lr": "Living Room"},
        devices_by_id={"d1": _dev()},
    )
    entity = _e(
        entity_id="light.living_room_lamp",
        name="Living Room Lamp",
        device_id="d1", area_id="lr",
    )
    assert rule.evaluate_all(entity, ctx) == []
