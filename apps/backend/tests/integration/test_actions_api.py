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
        ("d1", {"area_id": "living"}),
        ("d2", {"area_id": "living"}),
    ]


def test_rename_single(client, fake_ha):
    r = client.post(
        "/api/actions/rename",
        json={"device_id": "d2", "name_by_user": "bad_name"},
    )
    assert r.status_code == 200
    assert fake_ha.update_calls[-1] == ("d2", {"name_by_user": "bad_name"})


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
    assert fake_ha.update_calls == [("d1", {"name_by_user": "lr_room_lamp"})]
