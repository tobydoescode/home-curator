def test_acknowledge_entity_exception(client):
    r = client.post(
        "/api/exceptions",
        json={
            "entity_id": "light.kitchen_ceiling",
            "policy_id": "entity-missing-area",
            "note": "known low priority",
        },
    )
    assert r.status_code == 201


def test_clear_entity_exception(client):
    client.post(
        "/api/exceptions",
        json={"entity_id": "light.kitchen_ceiling", "policy_id": "entity-missing-area"},
    )
    r = client.delete("/api/exceptions/entity/light.kitchen_ceiling/entity-missing-area")
    assert r.status_code == 204

    # Listing shows nothing for this entity.
    r = client.get("/api/exceptions/list", params={"entity_id": "light.kitchen_ceiling"})
    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_list_exceptions_mixed_target(client):
    # Two device exceptions + one entity exception.
    client.post(
        "/api/exceptions", json={"device_id": "d1", "policy_id": "missing-room"},
    )
    client.post(
        "/api/exceptions", json={"device_id": "d2", "policy_id": "missing-room"},
    )
    client.post(
        "/api/exceptions",
        json={"entity_id": "light.kitchen_ceiling", "policy_id": "entity-missing-area"},
    )
    r = client.get("/api/exceptions/list")
    body = r.json()
    assert body["total"] == 3

    by_kind: dict[str, list] = {}
    for row in body["exceptions"]:
        by_kind.setdefault(row["target_kind"], []).append(row)
    assert len(by_kind["device"]) == 2
    assert len(by_kind["entity"]) == 1
    entity_row = by_kind["entity"][0]
    assert entity_row["entity_id"] == "light.kitchen_ceiling"
    # target_name is populated from the entity's display_name.
    assert entity_row["target_name"] == "Kitchen Ceiling"
    # target_area_name from entity area join.
    assert entity_row["target_area_name"] == "Kitchen"


def test_list_exceptions_filter_by_entity_id_only(client):
    client.post(
        "/api/exceptions", json={"device_id": "d1", "policy_id": "missing-room"},
    )
    client.post(
        "/api/exceptions",
        json={"entity_id": "light.kitchen_ceiling", "policy_id": "entity-missing-area"},
    )
    r = client.get("/api/exceptions/list", params={"entity_id": "light.kitchen_ceiling"})
    body = r.json()
    assert body["total"] == 1
    assert body["exceptions"][0]["target_kind"] == "entity"


def test_list_exceptions_filter_by_device_id_only(client):
    client.post(
        "/api/exceptions", json={"device_id": "d1", "policy_id": "missing-room"},
    )
    client.post(
        "/api/exceptions",
        json={"entity_id": "light.kitchen_ceiling", "policy_id": "entity-missing-area"},
    )
    r = client.get("/api/exceptions/list", params={"device_id": "d1"})
    body = r.json()
    assert body["total"] == 1
    assert body["exceptions"][0]["target_kind"] == "device"


def test_legacy_device_post_still_works(client):
    # Backwards-compat: a body with only device_id keeps working unchanged.
    r = client.post(
        "/api/exceptions",
        json={"device_id": "d1", "policy_id": "missing-room"},
    )
    assert r.status_code == 201
    r = client.get("/api/exceptions/list", params={"device_id": "d1"})
    body = r.json()
    assert body["total"] == 1
    row = body["exceptions"][0]
    # Legacy keys still populated.
    assert row["device_name"] == "living_room_lamp"
    assert row["target_kind"] == "device"
