def test_patch_entity_name_only(client, fake_ha):
    r = client.patch(
        "/api/actions/entity/light.kitchen_ceiling",
        json={"name": "Main Ceiling"},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert fake_ha.update_entity_calls[-1] == (
        "light.kitchen_ceiling",
        {"name": "Main Ceiling"},
    )


def test_patch_entity_rename_slug(client, fake_ha):
    r = client.patch(
        "/api/actions/entity/light.kitchen_ceiling",
        json={"new_entity_id": "light.study_lamp"},
    )
    assert r.status_code == 200
    assert fake_ha.update_entity_calls[-1] == (
        "light.kitchen_ceiling",
        {"new_entity_id": "light.study_lamp"},
    )


def test_patch_entity_batches_fields_into_one_call(client, fake_ha):
    before = len(fake_ha.update_entity_calls)
    r = client.patch(
        "/api/actions/entity/light.kitchen_ceiling",
        json={"name": "Main Ceiling", "area_id": "living", "icon": None},
    )
    assert r.status_code == 200
    assert len(fake_ha.update_entity_calls) == before + 1
    assert fake_ha.update_entity_calls[-1] == (
        "light.kitchen_ceiling",
        {"name": "Main Ceiling", "area_id": "living", "icon": None},
    )


def test_patch_entity_empty_body_rejected(client, fake_ha):
    before = len(fake_ha.update_entity_calls)
    r = client.patch("/api/actions/entity/light.kitchen_ceiling", json={})
    assert r.status_code == 400
    assert len(fake_ha.update_entity_calls) == before


def test_patch_entity_extra_field_forbidden(client):
    r = client.patch(
        "/api/actions/entity/light.kitchen_ceiling",
        json={"name": "x", "bogus": 1},
    )
    assert r.status_code == 422


def test_patch_entity_ha_error_surfaces_as_502(client, fake_ha):
    async def boom(eid, changes):
        del eid, changes
        raise RuntimeError("ha refused")

    fake_ha.update_entity = boom  # type: ignore[method-assign]
    r = client.patch(
        "/api/actions/entity/light.kitchen_ceiling",
        json={"name": "x"},
    )
    assert r.status_code == 502
    assert "ha refused" in r.json()["detail"]


# --- assign-room-entities (Phase 5) ----------------------------------------

def test_assign_room_entities_bulk(client, fake_ha):
    r = client.post(
        "/api/actions/assign-room-entities",
        json={
            "entity_ids": ["light.kitchen_ceiling", "sensor.temperature"],
            "area_id": "living",
        },
    )
    assert r.status_code == 200
    rows = r.json()["results"]
    assert rows == [
        {"entity_id": "light.kitchen_ceiling", "ok": True},
        {"entity_id": "sensor.temperature", "ok": True},
    ]
    assert fake_ha.update_entity_calls[-2:] == [
        ("light.kitchen_ceiling", {"area_id": "living"}),
        ("sensor.temperature", {"area_id": "living"}),
    ]


def test_assign_room_entities_partial_failure(client, fake_ha):
    original = fake_ha.update_entity

    async def flaky(eid, changes):
        if eid == "sensor.temperature":
            raise RuntimeError("integration refused")
        await original(eid, changes)

    fake_ha.update_entity = flaky  # type: ignore[method-assign]

    r = client.post(
        "/api/actions/assign-room-entities",
        json={
            "entity_ids": ["light.kitchen_ceiling", "sensor.temperature"],
            "area_id": "living",
        },
    )
    assert r.status_code == 200
    rows = {row["entity_id"]: row for row in r.json()["results"]}
    assert rows["light.kitchen_ceiling"] == {
        "entity_id": "light.kitchen_ceiling", "ok": True,
    }
    assert rows["sensor.temperature"]["ok"] is False
    assert "integration refused" in rows["sensor.temperature"]["error"]
