"""Four-combo matrix: require_own_area strict/lenient × entity.area_id
present/absent × device.area_id present/absent."""
import pytest

from home_curator.policies.schema import EntityMissingAreaPolicy
from home_curator.rules.base import Device, Entity, EvaluationContext
from home_curator.rules.missing_area import compile_entity_missing_area


def _entity(**kw):
    defaults = dict(
        entity_id="light.x", name="x", original_name=None, icon=None,
        domain="light", platform="hue", device_id=None, area_id=None,
        area_name=None, disabled_by=None, hidden_by=None, unique_id=None,
        created_at=None, modified_at=None, state={},
    )
    defaults.update(kw)
    return Entity(**defaults)


def _device(**kw):
    defaults = dict(
        id="d1", name="D", name_by_user=None, manufacturer=None, model=None,
        area_id=None, area_name=None, integration=None, disabled_by=None, entities=[],
    )
    defaults.update(kw)
    return Device(**defaults)


def _ctx(devices=None, exc=None):
    return EvaluationContext(
        area_name_to_id={}, area_id_to_name={}, exceptions=exc or set(),
        devices_by_id={d.id: d for d in (devices or [])},
    )


def _policy(require_own_area: bool) -> EntityMissingAreaPolicy:
    return EntityMissingAreaPolicy.model_validate({
        "id": "ma", "type": "entity_missing_area", "severity": "info",
        "require_own_area": require_own_area,
    })


@pytest.mark.parametrize(
    "require_own,entity_area,device_area,should_fire",
    [
        # Lenient: device fallback counts.
        (False, None,   None,   True),   # nothing set anywhere
        (False, None,   "k",    False),  # device has area — lenient passes
        (False, "k",    None,   False),  # entity has area
        (False, "k",    "k",    False),  # both set
        # Strict: only entity.area_id matters.
        (True,  None,   None,   True),
        (True,  None,   "k",    True),   # device area doesn't save us
        (True,  "k",    None,   False),
        (True,  "k",    "k",    False),
    ],
)
def test_entity_missing_area_matrix(require_own, entity_area, device_area, should_fire):
    p = _policy(require_own_area=require_own)
    rule = compile_entity_missing_area(p)
    dev = _device(id="d1", area_id=device_area)
    e = _entity(device_id="d1", area_id=entity_area)
    ctx = _ctx(devices=[dev])
    issue = rule.evaluate(e, ctx)
    if should_fire:
        assert issue is not None
        assert issue.policy_id == "ma"
        assert issue.target_kind == "entity"
        assert issue.target_id == "light.x"
    else:
        assert issue is None


def test_entity_missing_area_standalone_entity_fires_when_no_area():
    """Standalone entity (device_id=None) with no area fires regardless of mode."""
    for mode in (False, True):
        rule = compile_entity_missing_area(_policy(require_own_area=mode))
        e = _entity(device_id=None, area_id=None)
        assert rule.evaluate(e, _ctx()) is not None


def test_entity_missing_area_respects_exception():
    rule = compile_entity_missing_area(_policy(require_own_area=False))
    e = _entity(entity_id="light.x", area_id=None, device_id=None)
    ctx = _ctx(exc={("entity", "light.x", "ma")})
    assert rule.evaluate(e, ctx) is None


def test_entity_missing_area_disabled_returns_none():
    p = EntityMissingAreaPolicy.model_validate({
        "id": "ma", "type": "entity_missing_area", "severity": "info",
        "enabled": False, "require_own_area": True,
    })
    rule = compile_entity_missing_area(p)
    assert rule.evaluate(_entity(area_id=None), _ctx()) is None


def test_entity_missing_area_scope_is_entities():
    p = EntityMissingAreaPolicy.model_validate({
        "id": "ma", "type": "entity_missing_area", "severity": "info",
    })
    rule = compile_entity_missing_area(p)
    assert rule.scope == "entities"
