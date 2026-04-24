from home_curator.ha_client.models import HADeviceUpdate


def test_assign_room_bulk(client, fake_ha):
    r = client.post(
        "/api/actions/assign-room",
        json={"device_ids": ["d1", "d2"], "area_id": "living"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["results"] == [
        {"device_id": "d1", "ok": True},
        {"device_id": "d2", "ok": True},
    ]
    assert fake_ha.update_calls == [
        ("d1", HADeviceUpdate(area_id="living")),
        ("d2", HADeviceUpdate(area_id="living")),
    ]


def test_rename_single(client, fake_ha):
    r = client.post(
        "/api/actions/rename",
        json={"device_id": "d2", "name_by_user": "bad_name"},
    )
    assert r.status_code == 200
    assert fake_ha.update_calls[-1] == ("d2", HADeviceUpdate(name_by_user="bad_name"))


def test_rename_pattern_applies_to_multiple(client, fake_ha):
    r = client.post(
        "/api/actions/rename-pattern",
        json={
            "device_ids": ["d1", "d2"],
            "pattern": "^living_",
            "replacement": "lr_",
            "dry_run": False,
        },
    )
    assert r.status_code == 200
    results = {x["device_id"]: x for x in r.json()["results"]}
    assert results["d1"]["new_name"] == "lr_room_lamp"
    assert results["d1"]["ok"] is True
    assert results["d2"]["matched"] is False
    # Only d1 matched, so only one write call recorded
    assert fake_ha.update_calls == [("d1", HADeviceUpdate(name_by_user="lr_room_lamp"))]


def test_patch_device_name_only(client, fake_ha):
    r = client.patch(
        "/api/actions/device/d1",
        json={"name_by_user": "Lounge Lamp"},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert fake_ha.update_calls[-1] == ("d1", HADeviceUpdate(name_by_user="Lounge Lamp"))


def test_patch_device_area_only(client, fake_ha):
    r = client.patch(
        "/api/actions/device/d2",
        json={"area_id": "living"},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert fake_ha.update_calls[-1] == ("d2", HADeviceUpdate(area_id="living"))


def test_patch_device_both_fields_single_call(client, fake_ha):
    before = len(fake_ha.update_calls)
    r = client.patch(
        "/api/actions/device/d1",
        json={"name_by_user": "Main Lamp", "area_id": None},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    # Exactly one HA write for the combined change (verifies batching).
    assert len(fake_ha.update_calls) == before + 1
    assert fake_ha.update_calls[-1] == (
        "d1",
        HADeviceUpdate(name_by_user="Main Lamp", area_id=None),
    )


def test_patch_device_empty_body_rejected(client, fake_ha):
    before = len(fake_ha.update_calls)
    r = client.patch("/api/actions/device/d1", json={})
    assert r.status_code == 400
    # No HA write when the body has nothing to apply.
    assert len(fake_ha.update_calls) == before


def test_patch_device_ha_error_surfaces_as_502(client, fake_ha):
    async def boom(device_id, changes):
        del device_id, changes
        raise RuntimeError("ha unavailable")

    fake_ha.update_device = boom  # type: ignore[method-assign]
    r = client.patch(
        "/api/actions/device/d1",
        json={"name_by_user": "x"},
    )
    assert r.status_code == 502


def test_delete_single_device_ok(client, fake_ha):
    r = client.post(
        "/api/actions/delete",
        json={"device_ids": ["d1"]},
    )
    assert r.status_code == 200
    assert r.json() == {"results": [{"device_id": "d1", "ok": True}]}
    assert fake_ha.delete_calls == ["d1"]


def test_delete_bulk_partial_failure(client, fake_ha):
    # Make d2's delete fail; d1 still succeeds.
    original = fake_ha.delete_device

    async def flaky(device_id):
        if device_id == "d2":
            raise RuntimeError("integration refused removal")
        await original(device_id)

    fake_ha.delete_device = flaky  # type: ignore[method-assign]

    r = client.post(
        "/api/actions/delete",
        json={"device_ids": ["d1", "d2"]},
    )
    assert r.status_code == 200
    rows = {row["device_id"]: row for row in r.json()["results"]}
    assert rows["d1"] == {"device_id": "d1", "ok": True}
    assert rows["d2"]["ok"] is False
    assert "integration refused removal" in rows["d2"]["error"]


def test_delete_empty_body_rejected(client, fake_ha):
    before = len(fake_ha.delete_calls)
    r = client.post("/api/actions/delete", json={"device_ids": []})
    assert r.status_code == 400
    assert len(fake_ha.delete_calls) == before


def test_delete_unknown_device_id(client, fake_ha):
    r = client.post(
        "/api/actions/delete",
        json={"device_ids": ["ghost"]},
    )
    assert r.status_code == 200
    assert r.json() == {
        "results": [{"device_id": "ghost", "ok": False, "error": "device not found"}]
    }
    assert "ghost" not in fake_ha.delete_calls
