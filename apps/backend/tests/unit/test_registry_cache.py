import pytest

from home_curator.ha_client.fake import FakeHAClient
from home_curator.ha_client.models import HAArea, HADevice, HADeviceEntityRef
from home_curator.registry_cache.cache import RegistryCache


@pytest.mark.asyncio
async def test_load_populates_cache():
    fake = FakeHAClient(
        devices=[
            HADevice(
                id="d1",
                name="lamp",
                name_by_user=None,
                manufacturer=None,
                model=None,
                area_id="living",
                integration="hue",
                disabled_by=None,
                identifiers=[["hue", "abc"]],
                entities=[HADeviceEntityRef(id="light.lamp", domain="light")],
            )
        ],
        areas=[HAArea(id="living", name="Living Room")],
    )
    cache = RegistryCache(fake)
    await cache.load()
    devices = cache.devices()
    assert len(devices) == 1
    assert devices[0].area_name == "Living Room"
    assert cache.areas()[0].name == "Living Room"


@pytest.mark.asyncio
async def test_apply_delta_added():
    fake = FakeHAClient(devices=[], areas=[])
    cache = RegistryCache(fake)
    await cache.load()
    fake.set_devices(
        [
            HADevice(
                id="d1",
                name="new",
                name_by_user=None,
                manufacturer=None,
                model=None,
                area_id=None,
                integration=None,
                disabled_by=None,
                identifiers=[["x", "y"]],
                entities=[],
            )
        ]
    )
    diff = await cache.refresh()
    assert diff.added == ["d1"]
    assert diff.removed == []


@pytest.mark.asyncio
async def test_apply_delta_updated():
    """A device that stays but whose fields change appears in Diff.updated."""
    fake = FakeHAClient(
        devices=[
            HADevice(
                id="d1",
                name="old_name",
                name_by_user=None,
                manufacturer=None,
                model=None,
                area_id=None,
                integration=None,
                disabled_by=None,
                identifiers=[["x", "y"]],
                entities=[],
            )
        ],
        areas=[],
    )
    cache = RegistryCache(fake)
    await cache.load()

    fake.set_devices(
        [
            HADevice(
                id="d1",
                name="new_name",
                name_by_user=None,
                manufacturer=None,
                model=None,
                area_id=None,
                integration=None,
                disabled_by=None,
                identifiers=[["x", "y"]],
                entities=[],
            )
        ]
    )
    diff = await cache.refresh()
    assert diff.added == []
    assert diff.removed == []
    assert diff.updated == ["d1"]


@pytest.mark.asyncio
async def test_apply_delta_removed():
    fake = FakeHAClient(
        devices=[
            HADevice(
                id="d1",
                name="x",
                name_by_user=None,
                manufacturer=None,
                model=None,
                area_id=None,
                integration=None,
                disabled_by=None,
                identifiers=[["a", "b"]],
                entities=[],
            )
        ],
        areas=[],
    )
    cache = RegistryCache(fake)
    await cache.load()
    fake.set_devices([])
    diff = await cache.refresh()
    assert diff.removed == ["d1"]
