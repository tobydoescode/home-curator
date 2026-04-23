from home_curator.policies.schema import CustomPolicy
from home_curator.rules.base import Device, EvaluationContext
from home_curator.rules.custom_cel import compile_custom


def _d(**kw):
    defaults = dict(
        id="d1",
        name="n",
        name_by_user=None,
        manufacturer="Aqara",
        model=None,
        area_id=None,
        area_name=None,
        integration=None,
        disabled_by=None,
        entities=[],
    )
    defaults.update(kw)
    return Device(**defaults)


def _ctx(exc=None):
    return EvaluationContext(area_name_to_id={}, area_id_to_name={}, exceptions=exc or set())


def test_custom_fires_when_assert_false():
    p = CustomPolicy.model_validate(
        {
            "id": "c",
            "type": "custom",
            "enabled": True,
            "severity": "info",
            "scope": "devices",
            "when": 'device.manufacturer == "Aqara"',
            "assert": "device.area_id != null",
            "message": "Aqara needs room",
        }
    )
    rule = compile_custom(p)
    issue = rule.evaluate(_d(manufacturer="Aqara", area_id=None), _ctx())
    assert issue is not None
    assert issue.message == "Aqara needs room"


def test_when_gates_evaluation():
    p = CustomPolicy.model_validate(
        {
            "id": "c",
            "type": "custom",
            "enabled": True,
            "severity": "info",
            "scope": "devices",
            "when": 'device.manufacturer == "Ikea"',
            "assert": "device.area_id != null",
            "message": "msg",
        }
    )
    rule = compile_custom(p)
    assert rule.evaluate(_d(manufacturer="Aqara", area_id=None), _ctx()) is None


def test_assert_true_no_issue():
    p = CustomPolicy.model_validate(
        {
            "id": "c",
            "type": "custom",
            "enabled": True,
            "severity": "info",
            "scope": "devices",
            "assert": "device.area_id != null",
            "message": "msg",
        }
    )
    rule = compile_custom(p)
    assert rule.evaluate(_d(area_id="kitchen"), _ctx()) is None


def test_compile_error_on_bad_syntax():
    p = CustomPolicy.model_validate(
        {
            "id": "c",
            "type": "custom",
            "enabled": True,
            "severity": "info",
            "scope": "devices",
            "assert": "device.",
            "message": "msg",
        }
    )
    rule = compile_custom(p)
    assert rule.compile_error is not None
    # Must not raise at evaluation; just return None
    assert rule.evaluate(_d(), _ctx()) is None


def test_runtime_error_counted():
    # Access field that doesn't exist should be caught and counted
    p = CustomPolicy.model_validate(
        {
            "id": "c",
            "type": "custom",
            "enabled": True,
            "severity": "info",
            "scope": "devices",
            "assert": "device.does_not_exist == 1",
            "message": "msg",
        }
    )
    rule = compile_custom(p)
    rule.evaluate(_d(), _ctx())
    assert rule.runtime_errors >= 1


def test_exception_suppresses():
    p = CustomPolicy.model_validate(
        {
            "id": "c",
            "type": "custom",
            "enabled": True,
            "severity": "info",
            "scope": "devices",
            "assert": "device.area_id != null",
            "message": "msg",
        }
    )
    rule = compile_custom(p)
    assert rule.evaluate(_d(area_id=None), _ctx(exc={("device", "d1", "c")})) is None


def test_disabled_rule_does_not_fire():
    p = CustomPolicy.model_validate(
        {
            "id": "c",
            "type": "custom",
            "enabled": False,
            "severity": "info",
            "scope": "devices",
            "assert": "device.area_id != null",
            "message": "msg",
        }
    )
    rule = compile_custom(p)
    assert rule.evaluate(_d(area_id=None), _ctx()) is None


def test_runtime_errors_capped():
    from home_curator.rules.custom_cel import MAX_RUNTIME_ERRORS

    p = CustomPolicy.model_validate(
        {
            "id": "c",
            "type": "custom",
            "enabled": True,
            "severity": "info",
            "scope": "devices",
            "assert": "device.does_not_exist == 1",
            "message": "msg",
        }
    )
    rule = compile_custom(p)
    # Evaluate MAX + 10 times; counter should stop at MAX
    for _ in range(MAX_RUNTIME_ERRORS + 10):
        rule.evaluate(_d(), _ctx())
    assert rule.runtime_errors == MAX_RUNTIME_ERRORS
