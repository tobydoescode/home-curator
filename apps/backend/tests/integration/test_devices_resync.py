"""POST /api/cache/resync — user-triggered force refresh."""

from home_curator.ha_client.models import HADevice, HADeviceEntityRef


def test_resync_no_changes_returns_zero_diff(client, fake_ha):
    """When HA state matches the cache, every counter is 0."""
    before_calls = len(fake_ha.update_calls)
    r = client.post("/api/cache/resync")
    assert r.status_code == 200
    body = r.json()
    assert body["added"] == 0
    assert body["removed"] == 0
    assert body["updated"] == 0
    # Entity fields default to 0; present for backwards-compatibility check.
    assert body["entity_added"] == 0
    assert body["entity_removed"] == 0
    assert body["entity_updated"] == 0
    # Resync is read-only — it must not trigger writes back to HA.
    assert len(fake_ha.update_calls) == before_calls


def test_resync_reflects_added_removed_updated(client, fake_ha):
    """Mutating the fake HA then resyncing reports counts per bucket."""
    # Baseline: d1 (living_room_lamp) and d2 (BadCase) are in the cache.
    # Change the fake's state: remove d2, add d3, rename d1.
    fake_ha.set_devices([
        HADevice(
            id="d1",
            name="living_room_lamp",
            name_by_user="Lounge Lamp",
            manufacturer="Signify",
            model="m",
            area_id="living",
            integration="hue",
            disabled_by=None,
            identifiers=[["hue", "a"]],
            entities=[HADeviceEntityRef(id="light.lamp", domain="light")],
        ),
        HADevice(
            id="d3",
            name="new_device",
            name_by_user=None,
            manufacturer="Nanoleaf",
            model="x",
            area_id=None,
            integration="nanoleaf",
            disabled_by=None,
            identifiers=[["nanoleaf", "c"]],
            entities=[],
        ),
    ])
    r = client.post("/api/cache/resync")
    assert r.status_code == 200
    body = r.json()
    assert body["added"] == 1
    assert body["removed"] == 1
    assert body["updated"] == 1


def test_resync_ha_error_returns_502(client, fake_ha):
    """If `cache.refresh()` raises (via the HA client), return 502 with a
    meaningful `detail`, mirroring the existing PATCH-device error shape."""

    async def boom():
        raise RuntimeError("ha unavailable")

    fake_ha.get_devices = boom  # type: ignore[method-assign]
    r = client.post("/api/cache/resync")
    assert r.status_code == 502
    assert "resync failed" in r.json()["detail"]
    assert "ha unavailable" in r.json()["detail"]
