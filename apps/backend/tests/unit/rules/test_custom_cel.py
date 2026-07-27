from typing import Any

from home_curator.policies.schema import CustomPolicy
from home_curator.rules.custom_cel import compile_custom
from tests.unit.rules.factories import make_context as _ctx
from tests.unit.rules.factories import make_device


def _d(**kwargs: Any):
    manufacturer = kwargs.pop("manufacturer", "Aqara")
    return make_device(manufacturer=manufacturer, **kwargs)


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
    # A CEL runtime error must not escape; the rule simply reports no issue.
    assert rule.evaluate(_d(), _ctx()) is None


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


def test_repeated_runtime_errors_stay_contained():
    """A bad expression firing against every device must not accumulate state.

    This previously incremented a counter nothing read, which also meant
    `evaluate` mutated the shared compiled rule from FastAPI's threadpool.
    """
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

    for _ in range(100):
        assert rule.evaluate(_d(), _ctx()) is None
