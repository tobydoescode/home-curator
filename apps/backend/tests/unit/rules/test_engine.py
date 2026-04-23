from home_curator.policies.schema import PoliciesFile
from home_curator.rules.base import Device, EvaluationContext
from home_curator.rules.engine import RuleEngine


def _device(**kw):
    d = dict(
        id="d",
        name="bad-name",
        name_by_user=None,
        manufacturer=None,
        model=None,
        area_id=None,
        area_name=None,
        integration=None,
        disabled_by=None,
        entities=[],
    )
    d.update(kw)
    return Device(**d)


def _empty_ctx():
    return EvaluationContext(area_name_to_id={}, area_id_to_name={}, exceptions=set())


def test_engine_evaluates_all_policies():
    file_ = PoliciesFile.model_validate(
        {
            "version": 1,
            "policies": [
                {"id": "a", "type": "missing_area", "enabled": True, "severity": "warning"},
                {
                    "id": "n",
                    "type": "naming_convention",
                    "enabled": True,
                    "severity": "warning",
                    "global": {"preset": "snake_case"},
                    "rooms": [],
                },
            ],
        }
    )
    ctx = _empty_ctx()
    engine = RuleEngine.compile(file_, ctx)
    issues = engine.evaluate(_device(), ctx)
    ids = sorted(i.policy_id for i in issues)
    assert ids == ["a", "n"]


def test_disabled_policy_skipped():
    file_ = PoliciesFile.model_validate(
        {
            "version": 1,
            "policies": [
                {"id": "a", "type": "missing_area", "enabled": False, "severity": "warning"},
            ],
        }
    )
    ctx = _empty_ctx()
    engine = RuleEngine.compile(file_, ctx)
    assert engine.evaluate(_device(), ctx) == []


def test_all_existing_compiled_rules_default_scope_devices():
    """Every compiled rule class must expose a 'scope' attribute. Existing
    device rules must keep device scope so nothing regresses."""
    file_ = PoliciesFile.model_validate({
        "version": 1,
        "policies": [
            {"id": "a", "type": "missing_area", "severity": "warning"},
            {
                "id": "n", "type": "naming_convention", "severity": "warning",
                "global": {"preset": "snake_case"}, "rooms": [],
            },
            {"id": "r", "type": "reappeared_after_delete", "severity": "info"},
            {
                "id": "c", "type": "custom", "severity": "info",
                "assert": "device.area_id != null", "message": "m",
            },
        ],
    })
    ctx = _empty_ctx()
    engine = RuleEngine.compile(file_, ctx)
    for rule in engine.compiled:
        assert rule.scope == "devices", rule


def test_errored_custom_policy_does_not_crash():
    file_ = PoliciesFile.model_validate(
        {
            "version": 1,
            "policies": [
                {"id": "a", "type": "missing_area", "enabled": True, "severity": "warning"},
                {
                    "id": "c",
                    "type": "custom",
                    "enabled": True,
                    "severity": "info",
                    "scope": "devices",
                    "assert": "bad syntax.",
                    "message": "x",
                },
            ],
        }
    )
    ctx = _empty_ctx()
    engine = RuleEngine.compile(file_, ctx)
    issues = engine.evaluate(_device(), ctx)
    # missing_area still fires, custom is skipped due to compile error
    assert [i.policy_id for i in issues] == ["a"]
    errs = engine.compile_errors()
    assert "c" in errs
    assert "CEL" in errs["c"]


def test_exception_suppresses_issue_end_to_end():
    """Without ctx.exceptions the default ctx wouldn't have filtered this.
    Exercises the real-ctx code path after dropping the evaluate() default."""
    file_ = PoliciesFile.model_validate(
        {
            "version": 1,
            "policies": [
                {"id": "a", "type": "missing_area", "enabled": True, "severity": "warning"},
            ],
        }
    )
    ctx = EvaluationContext(
        area_name_to_id={}, area_id_to_name={}, exceptions={("device", "d", "a")}
    )
    engine = RuleEngine.compile(file_, ctx)
    assert engine.evaluate(_device(), ctx) == []
