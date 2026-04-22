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


def test_issue_equality():
    a = Issue("p1", "missing_area", "warning", "msg", "abc")
    b = Issue("p1", "missing_area", "warning", "msg", "abc")
    assert a == b


def test_evaluation_context():
    ctx = EvaluationContext(
        area_name_to_id={"garage": "garage_xyz"},
        area_id_to_name={"garage_xyz": "Garage"},
        exceptions=set(),
    )
    assert ctx.resolve_area_id_from_name("Garage") == "garage_xyz"
    assert ctx.resolve_area_id_from_name("Unknown") is None
