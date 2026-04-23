def test_list_entities_default_excludes_disabled_and_hidden(client):
    r = client.get("/api/entities")
    assert r.status_code == 200
    body = r.json()
    ids = {e["entity_id"] for e in body["entities"]}
    # Baseline fixture has 6 entities; one disabled, one hidden.
    # Default must omit them.
    assert "switch.garage_door" not in ids
    assert "binary_sensor.kitchen_motion" not in ids
    assert body["total"] == 4
    assert body["page"] == 1
    assert body["page_size"] == 50


def test_list_entities_carries_display_and_device_names(client):
    r = client.get("/api/entities", params={"q": "light.lamp"})
    assert r.status_code == 200
    [row] = r.json()["entities"]
    assert row["entity_id"] == "light.lamp"
    # name is null, original_name is "Living Room Lamp"
    assert row["display_name"] == "Living Room Lamp"
    # Device join populates device_name (d1's display name).
    assert row["device_name"] == "living_room_lamp"
    # Our fixture puts light.lamp with area_id=null; device d1 is in "living".
    # The API returns the entity's own area_id; the cache hydrates area_name
    # from the device fallback.
    assert row["area_id"] is None
