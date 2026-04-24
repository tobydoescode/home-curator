from home_curator.policies.schema import ReappearedAfterDeletePolicy
from home_curator.rules.base import Device, EvaluationContext
from home_curator.rules.reappeared_after_delete import compile_reappeared


def _d(state=None):
    return Device(
        id="d1",
        name="n",
        name_by_user=None,
        manufacturer=None,
        model=None,
        area_id=None,
        area_name=None,
        integration=None,
        disabled_by=None,
        entities=[],
        state=state or {},
    )


def _ctx(exc=None):
    return EvaluationContext(area_name_to_id={}, area_id_to_name={}, exceptions=exc or set())


def test_no_state_flag():
    p = ReappearedAfterDeletePolicy(
        id="r", type="reappeared_after_delete", enabled=True, severity="info"
    )
    r = compile_reappeared(p)
    assert r.evaluate(_d(state={"reappeared_after_delete": False}), _ctx()) is None


def test_state_flag_set():
    p = ReappearedAfterDeletePolicy(
        id="r", type="reappeared_after_delete", enabled=True, severity="info"
    )
    r = compile_reappeared(p)
    issue = r.evaluate(_d(state={"reappeared_after_delete": True}), _ctx())
    assert issue is not None
    assert "Reappeared" in issue.message


def test_exception_suppresses():
    p = ReappearedAfterDeletePolicy(
        id="r", type="reappeared_after_delete", enabled=True, severity="info"
    )
    r = compile_reappeared(p)
    ctx = _ctx(exc={("device", "d1", "r")})
    assert r.evaluate(_d(state={"reappeared_after_delete": True}), ctx) is None


def test_disabled_rule_does_not_fire():
    p = ReappearedAfterDeletePolicy(
        id="r", type="reappeared_after_delete", enabled=False, severity="info"
    )
    r = compile_reappeared(p)
    assert r.evaluate(_d(state={"reappeared_after_delete": True}), _ctx()) is None
