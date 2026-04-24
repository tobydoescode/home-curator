"""Entity-scope custom CEL rules: CEL variable is `entity`, context has
`entity.device` when owned / null when standalone, and `_state` is readable."""
from typing import Any

from home_curator.policies.schema import CustomPolicy
from home_curator.rules.custom_cel import compile_custom
from tests.unit.rules.factories import make_context, make_device, make_entity


def _entity(**kwargs: Any):
    return make_entity(**kwargs)


def _device(**kwargs: Any):
    return make_device(
        name=kwargs.pop("name", "Kitchen Hub"),
        manufacturer=kwargs.pop("manufacturer", "hue"),
        area_id=kwargs.pop("area_id", "k"),
        area_name=kwargs.pop("area_name", "Kitchen"),
        integration=kwargs.pop("integration", "hue"),
        **kwargs,
    )


def _ctx(devices=None, exc=None):
    return make_context(
        area_id_to_name={"k": "Kitchen"},
        exc=exc,
        devices=devices,
    )


def test_entity_cel_uses_entity_variable():
    p = CustomPolicy.model_validate({
        "id": "c", "type": "custom", "severity": "info", "scope": "entities",
        "assert": "entity.domain == 'light'", "message": "m",
    })
    rule = compile_custom(p)
    # light entity passes the assert → no issue.
    assert rule.evaluate(_entity(domain="light"), _ctx()) is None
    # non-light fires.
    issue = rule.evaluate(_entity(domain="switch"), _ctx())
    assert issue is not None


def test_entity_cel_device_null_when_standalone():
    p = CustomPolicy.model_validate({
        "id": "c", "type": "custom", "severity": "info", "scope": "entities",
        "assert": "entity.device == null", "message": "m",
    })
    rule = compile_custom(p)
    # device_id is None → entity.device must be null → assert holds → no issue.
    assert rule.evaluate(_entity(device_id=None), _ctx()) is None


def test_entity_cel_device_populated_when_owned():
    """entity.device carries the owning device's context dict when device_id
    resolves in ctx."""
    p = CustomPolicy.model_validate({
        "id": "c", "type": "custom", "severity": "info", "scope": "entities",
        "assert": "entity.device.manufacturer == 'hue'", "message": "m",
    })
    rule = compile_custom(p)
    dev = _device(id="d1", manufacturer="hue")
    # Entity owned by dev — context wiring makes entity.device.manufacturer readable.
    assert rule.evaluate(_entity(device_id="d1"), _ctx(devices=[dev])) is None


def test_entity_cel_state_reappeared_readable():
    p = CustomPolicy.model_validate({
        "id": "c", "type": "custom", "severity": "info", "scope": "entities",
        "assert": "entity._state.reappeared_after_delete == false", "message": "m",
    })
    rule = compile_custom(p)
    # state flag true → assert fails → issue fires.
    e = _entity(state={"reappeared_after_delete": True})
    issue = rule.evaluate(e, _ctx())
    assert issue is not None


def test_entity_cel_area_name_resolved_via_ctx():
    p = CustomPolicy.model_validate({
        "id": "c", "type": "custom", "severity": "info", "scope": "entities",
        "assert": "entity.area_name == 'Kitchen'", "message": "m",
    })
    rule = compile_custom(p)
    ctx = _ctx()  # area_id_to_name contains "k" → "Kitchen"
    # Entity area_id='k' → area_name resolved → assert holds → no issue.
    assert rule.evaluate(_entity(area_id="k"), ctx) is None


def test_entity_cel_exception_suppresses():
    p = CustomPolicy.model_validate({
        "id": "c", "type": "custom", "severity": "info", "scope": "entities",
        "assert": "false", "message": "m",
    })
    rule = compile_custom(p)
    ctx = _ctx(exc={("entity", "light.x", "c")})
    # Exception key matches → suppressed even though assert would fire.
    assert rule.evaluate(_entity(), ctx) is None


def test_entity_cel_issue_has_entity_target():
    """Fired entity-scope issue carries target_kind='entity', target_id=entity_id."""
    p = CustomPolicy.model_validate({
        "id": "c", "type": "custom", "severity": "info", "scope": "entities",
        "assert": "false", "message": "m",
    })
    rule = compile_custom(p)
    issue = rule.evaluate(_entity(entity_id="light.kitchen_lamp"), _ctx())
    assert issue is not None
    assert issue.target_kind == "entity"
    assert issue.target_id == "light.kitchen_lamp"
