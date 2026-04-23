"""Entity-scope variant of reappeared_after_delete. Shape mirrors the
device path exactly, keyed by entity.entity_id + policy id."""
from home_curator.policies.schema import ReappearedAfterDeletePolicy
from home_curator.rules.base import Entity, EvaluationContext
from home_curator.rules.reappeared_after_delete import compile_reappeared


def _e(state=None):
    return Entity(
        entity_id="light.x", name="x", original_name=None, icon=None,
        domain="light", platform="hue", device_id=None, area_id=None,
        area_name=None, disabled_by=None, hidden_by=None, unique_id=None,
        created_at=None, modified_at=None, state=state or {},
    )


def _ctx(exc=None):
    return EvaluationContext(
        area_name_to_id={}, area_id_to_name={}, exceptions=exc or set(),
        devices_by_id={},
    )


def test_entity_no_state_flag():
    p = ReappearedAfterDeletePolicy.model_validate({
        "id": "r", "type": "reappeared_after_delete", "severity": "info",
        "scope": "entities",
    })
    r = compile_reappeared(p)
    assert r.evaluate(_e(state={"reappeared_after_delete": False}), _ctx()) is None


def test_entity_state_flag_set():
    p = ReappearedAfterDeletePolicy.model_validate({
        "id": "r", "type": "reappeared_after_delete", "severity": "info",
        "scope": "entities",
    })
    r = compile_reappeared(p)
    issue = r.evaluate(_e(state={"reappeared_after_delete": True}), _ctx())
    assert issue is not None
    assert "Reappeared" in issue.message
    assert issue.target_kind == "entity"
    assert issue.target_id == "light.x"


def test_entity_exception_suppresses():
    p = ReappearedAfterDeletePolicy.model_validate({
        "id": "r", "type": "reappeared_after_delete", "severity": "info",
        "scope": "entities",
    })
    r = compile_reappeared(p)
    ctx = _ctx(exc={("entity", "light.x", "r")})
    assert r.evaluate(_e(state={"reappeared_after_delete": True}), ctx) is None


def test_entity_scope_is_entities_on_compiled():
    """Scope attribute flows from policy.scope to compiled rule."""
    p = ReappearedAfterDeletePolicy.model_validate({
        "id": "r", "type": "reappeared_after_delete", "severity": "info",
        "scope": "entities",
    })
    r = compile_reappeared(p)
    assert r.scope == "entities"


def test_device_scope_still_default_when_unspecified():
    p = ReappearedAfterDeletePolicy.model_validate({
        "id": "r", "type": "reappeared_after_delete", "severity": "info",
    })
    r = compile_reappeared(p)
    assert r.scope == "devices"
