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
    engine = RuleEngine.compile(
        file_, EvaluationContext(area_name_to_id={}, area_id_to_name={}, exceptions=set())
    )
    issues = engine.evaluate(_device())
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
    engine = RuleEngine.compile(
        file_, EvaluationContext(area_name_to_id={}, area_id_to_name={}, exceptions=set())
    )
    assert engine.evaluate(_device()) == []


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
                    "assert": "bad syntax.",
                    "message": "x",
                },
            ],
        }
    )
    engine = RuleEngine.compile(
        file_, EvaluationContext(area_name_to_id={}, area_id_to_name={}, exceptions=set())
    )
    issues = engine.evaluate(_device())
    # missing_area still fires, custom is skipped due to compile error
    assert [i.policy_id for i in issues] == ["a"]
    errs = engine.compile_errors()
    assert "c" in errs
    assert "CEL" in errs["c"]
