from home_curator.rules.base import Device, EvaluationContext, Issue


def test_device_shape():
    d = Device(
        id="abc",
        name="hue_bulb",
        name_by_user=None,
        manufacturer="Signify",
        model="LCT007",
        area_id=None,
        area_name=None,
        integration="hue",
        disabled_by=None,
        entities=[],
        state={"reappeared_after_delete": False},
    )
    assert d.name == "hue_bulb"
    assert d.state["reappeared_after_delete"] is False


def test_issue_equality_and_hashability():
    a = Issue("p1", "missing_area", "warning", "msg", "abc")
    b = Issue("p1", "missing_area", "warning", "msg", "abc")
    assert a == b
    assert hash(a) == hash(b)
    assert len({a, b}) == 1


def test_evaluation_context():
    ctx = EvaluationContext(
        area_name_to_id={"garage": "garage_xyz"},
        area_id_to_name={"garage_xyz": "Garage"},
        exceptions={("device", "d1", "p1")},
    )
    assert ctx.resolve_area_id_from_name("Garage") == "garage_xyz"
    assert ctx.resolve_area_id_from_name("Unknown") is None
    assert ("device", "d1", "p1") in ctx.exceptions
    assert ("device", "d1", "p2") not in ctx.exceptions


def test_to_cel_context_keys_and_state_prefix():
    d = Device(
        id="abc",
        name="n",
        name_by_user=None,
        manufacturer=None,
        model=None,
        area_id=None,
        area_name=None,
        integration=None,
        disabled_by=None,
        entities=[{"id": "light.a", "domain": "light"}],
        state={"reappeared_after_delete": True},
    )
    ctx = d.to_cel_context()
    assert set(ctx.keys()) == {
        "id", "name", "name_by_user", "manufacturer", "model",
        "area_id", "area_name", "integration", "disabled_by",
        "entities", "_state",
    }
    assert ctx["_state"] == {"reappeared_after_delete": True}
    assert "state" not in ctx
