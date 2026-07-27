"""Device writes against a real Home Assistant registry.

The container is shared across the session, so mutating tests either restore
what they changed or operate on a fixture reserved for them. The multi-entry
device exists solely for the destructive test here.
"""

from __future__ import annotations

import pytest

from home_curator.ha_client.models import HADeviceUpdate

pytestmark = pytest.mark.realha

MULTI_ENTRY_DEVICE_NAME = "multi_entry_device"


async def _device_by_name(ha_client, name: str):
    return next((d for d in await ha_client.get_devices() if d.name == name), None)


async def test_update_device_sets_name_by_user(ha_client):
    """Renaming sets `name_by_user` and leaves the integration's `name` alone."""
    before = await _device_by_name(ha_client, "living_room_lamp")
    assert before is not None
    assert before.name_by_user is None

    try:
        await ha_client.update_device(
            before.id, HADeviceUpdate(name_by_user="Renamed By Test")
        )
        after = next(d for d in await ha_client.get_devices() if d.id == before.id)
        assert after.name_by_user == "Renamed By Test"
        # `get_devices` folds name_by_user into `name`, which is what the
        # devices listing renders.
        assert after.name == "Renamed By Test"
    finally:
        await ha_client.update_device(before.id, HADeviceUpdate(name_by_user=None))

    restored = next(d for d in await ha_client.get_devices() if d.id == before.id)
    assert restored.name_by_user is None
    assert restored.name == "living_room_lamp"


async def test_update_device_assigns_area(ha_client):
    device = await _device_by_name(ha_client, "BadCase")
    assert device is not None
    assert device.area_id is None

    areas = {a.name: a.id for a in await ha_client.get_areas()}
    garage = areas["Garage"]

    try:
        await ha_client.update_device(device.id, HADeviceUpdate(area_id=garage))
        after = next(d for d in await ha_client.get_devices() if d.id == device.id)
        assert after.area_id == garage
    finally:
        await ha_client.update_device(device.id, HADeviceUpdate(area_id=None))

    restored = next(d for d in await ha_client.get_devices() if d.id == device.id)
    assert restored.area_id is None


async def test_update_device_rejects_unknown_device(ha_client):
    """HA errors are surfaced as exceptions rather than swallowed."""
    with pytest.raises(Exception):  # noqa: B017 - celpy-free path; HA raises RuntimeError
        await ha_client.update_device(
            "does-not-exist", HADeviceUpdate(name_by_user="nope")
        )


async def test_delete_device_unlinks_every_config_entry(ha_client):
    """The delete path walks all config entries on a device.

    `delete_device` has no HA "delete device" command to call — it removes the
    device from each owning config entry and relies on HA dropping the device
    once the last one goes. This fixture device is deliberately attached to
    two entries so that loop runs more than once.
    """
    device = await _device_by_name(ha_client, MULTI_ENTRY_DEVICE_NAME)
    assert device is not None, "fixture device missing"
    assert len(device.config_entries) == 2, (
        f"expected two config entries, got {device.config_entries}"
    )

    await ha_client.delete_device(device.id)

    assert await _device_by_name(ha_client, MULTI_ENTRY_DEVICE_NAME) is None


async def test_delete_device_rejects_unknown_device(ha_client):
    with pytest.raises(RuntimeError, match="not found in HA registry"):
        await ha_client.delete_device("does-not-exist")
