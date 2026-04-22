from home_curator.policies.schema import MissingAreaPolicy
from home_curator.rules.base import Device, EvaluationContext
from home_curator.rules.missing_area import compile_missing_area


def _device(area_id=None):
    return Device(
        id="d1",
        name="n",
        name_by_user=None,
        manufacturer=None,
        model=None,
        area_id=area_id,
        area_name=None,
        integration=None,
        disabled_by=None,
        entities=[],
    )


def _ctx(exc=None):
    return EvaluationContext(area_name_to_id={}, area_id_to_name={}, exceptions=exc or set())


def test_fires_when_no_area():
    p = MissingAreaPolicy(id="ma", type="missing_area", enabled=True, severity="warning")
    rule = compile_missing_area(p)
    issue = rule.evaluate(_device(area_id=None), _ctx())
    assert issue is not None
    assert issue.policy_id == "ma"
    assert issue.message == "Device Not Assigned To A Room"


def test_no_issue_when_area_present():
    p = MissingAreaPolicy(id="ma", type="missing_area", enabled=True, severity="warning")
    rule = compile_missing_area(p)
    assert rule.evaluate(_device(area_id="garage"), _ctx()) is None


def test_exception_suppresses():
    p = MissingAreaPolicy(id="ma", type="missing_area", enabled=True, severity="warning")
    rule = compile_missing_area(p)
    ctx = _ctx(exc={("d1", "ma")})
    assert rule.evaluate(_device(area_id=None), ctx) is None


def test_disabled_rule_does_not_fire():
    p = MissingAreaPolicy(id="ma", type="missing_area", enabled=False, severity="warning")
    rule = compile_missing_area(p)
    assert rule.evaluate(_device(area_id=None), _ctx()) is None
