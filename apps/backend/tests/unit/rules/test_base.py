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
    a = Issue("p1", "missing_area", "warning", "msg", "device", "abc")
    b = Issue("p1", "missing_area", "warning", "msg", "device", "abc")
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


def test_entity_to_cel_context_shape():
    """Entity.to_cel_context produces the shape custom_cel consumes."""
    from home_curator.rules.base import Entity

    e = Entity(
        entity_id="light.kitchen",
        name="Kitchen Light",
        original_name="Hue Bulb",
        icon=None,
        domain="light",
        platform="hue",
        device_id="d1",
        area_id="k",
        area_name=None,
        disabled_by=None,
        hidden_by=None,
        unique_id="hue-xyz",
        created_at=None,
        modified_at=None,
        state={"reappeared_after_delete": True},
    )
    ctx = e.to_cel_context(device_context=None, area_name="Kitchen")
    assert ctx["entity_id"] == "light.kitchen"
    assert ctx["name"] == "Kitchen Light"
    assert ctx["original_name"] == "Hue Bulb"
    assert ctx["domain"] == "light"
    assert ctx["platform"] == "hue"
    assert ctx["device_id"] == "d1"
    assert ctx["area_id"] == "k"
    # Caller passes area_name (resolved via ctx.area_id_to_name); context
    # surfaces that rather than the Entity's own area_name field so ad-hoc
    # device-owned area resolution wins.
    assert ctx["area_name"] == "Kitchen"
    assert ctx["disabled_by"] is None
    assert ctx["hidden_by"] is None
    assert ctx["icon"] is None
    # device is wired in by the caller — None for this standalone-style call.
    assert ctx["device"] is None
    # state surfaces under `_state` so computed flags (reappeared_after_delete)
    # are namespace-separated from registry fields.
    assert ctx["_state"]["reappeared_after_delete"] is True


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
