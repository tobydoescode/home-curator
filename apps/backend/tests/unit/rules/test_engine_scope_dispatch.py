"""Scope isolation: device-scoped rules never run against entities, and
vice versa. Uses custom rules (easiest to scope-label) as the probe."""
from home_curator.policies.schema import PoliciesFile
from home_curator.rules.base import Device, Entity, EvaluationContext
from home_curator.rules.engine import RuleEngine


def _device(**kw):
    defaults = dict(
        id="d1", name="d1", name_by_user=None, manufacturer=None,
        model=None, area_id=None, area_name=None, integration=None,
        disabled_by=None, entities=[],
    )
    defaults.update(kw)
    return Device(**defaults)


def _entity(**kw):
    defaults = dict(
        entity_id="light.x", name="x", original_name=None, icon=None,
        domain="light", platform="hue", device_id=None, area_id=None,
        area_name=None, disabled_by=None, hidden_by=None, unique_id=None,
        created_at=None, modified_at=None, state={},
    )
    defaults.update(kw)
    return Entity(**defaults)


def _ctx():
    return EvaluationContext(
        area_name_to_id={}, area_id_to_name={}, exceptions=set(),
    )


def test_device_scoped_rule_not_run_on_entity():
    """A custom device rule must never produce an Issue when the engine
    is evaluating an Entity."""
    file_ = PoliciesFile.model_validate({
        "version": 1,
        "policies": [
            {
                "id": "dev-rule", "type": "custom", "severity": "info",
                "scope": "devices",
                "assert": "false",  # would always fire if ever run
                "message": "never-for-entities",
            },
        ],
    })
    ctx = _ctx()
    engine = RuleEngine.compile(file_, ctx)
    # Entity passes through — the rule is device-scoped, skipped.
    assert engine.evaluate(_entity(), ctx) == []
    # Device fires — the rule applies here.
    issues = engine.evaluate(_device(), ctx)
    assert [i.policy_id for i in issues] == ["dev-rule"]


def test_entity_scoped_rule_not_run_on_device():
    file_ = PoliciesFile.model_validate({
        "version": 1,
        "policies": [
            {
                "id": "ent-rule", "type": "custom", "severity": "info",
                "scope": "entities",
                "assert": "false",
                "message": "never-for-devices",
            },
        ],
    })
    ctx = _ctx()
    engine = RuleEngine.compile(file_, ctx)
    # Device passes through — the rule is entity-scoped, skipped.
    assert engine.evaluate(_device(), ctx) == []
    # Entity fires.
    issues = engine.evaluate(_entity(), ctx)
    assert [i.policy_id for i in issues] == ["ent-rule"]


def test_mixed_scopes_each_fire_in_their_lane():
    file_ = PoliciesFile.model_validate({
        "version": 1,
        "policies": [
            {
                "id": "dev", "type": "custom", "severity": "info",
                "scope": "devices",
                "assert": "false", "message": "d",
            },
            {
                "id": "ent", "type": "custom", "severity": "info",
                "scope": "entities",
                "assert": "false", "message": "e",
            },
        ],
    })
    ctx = _ctx()
    engine = RuleEngine.compile(file_, ctx)
    assert [i.policy_id for i in engine.evaluate(_device(), ctx)] == ["dev"]
    assert [i.policy_id for i in engine.evaluate(_entity(), ctx)] == ["ent"]
