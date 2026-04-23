import pytest

from home_curator.ha_client.fake import FakeHAClient
from home_curator.registry_cache.cache import RegistryCache
from home_curator.registry_cache.entity_cache import EntityRegistryCache


def _ent(eid, device_id="d1", area_id=None, platform="hue", unique_id="x"):
    return {
        "entity_id": eid,
        "name": None,
        "original_name": eid,
        "icon": None,
        "platform": platform,
        "device_id": device_id,
        "area_id": area_id,
        "disabled_by": None,
        "hidden_by": None,
        "unique_id": unique_id,
    }


def _dev(did, area_id=None):
    return {
        "id": did,
        "name": did,
        "name_by_user": None,
        "manufacturer": None,
        "model": None,
        "area_id": area_id,
        "integration": None,
        "disabled_by": None,
        "identifiers": [[did, "x"]],
        "entities": [],
    }


@pytest.mark.asyncio
async def test_load_indexes_entities_by_id_and_hydrates_area_name():
    fake = FakeHAClient(
        devices=[_dev("d1", area_id="kitchen")],
        areas=[{"id": "kitchen", "name": "Kitchen"}],
        entities=[_ent("light.kitchen_lamp", device_id="d1", area_id=None)],
    )
    dev_cache = RegistryCache(fake)
    await dev_cache.load()
    cache = EntityRegistryCache(fake, area_lookup=dev_cache.area_id_to_name, device_lookup=dev_cache.device)
    await cache.load()

    ents = cache.entities()
    assert len(ents) == 1
    e = ents[0]
    assert e.entity_id == "light.kitchen_lamp"
    assert e.domain == "light"
    # Entity has no own area → inherits from device's area ID lookup for display.
    assert e.area_id is None
    # area_name reflects the effective area (device's), computed once at load.
    assert e.area_name == "Kitchen"


@pytest.mark.asyncio
async def test_entity_lookup_by_id_returns_none_when_unknown():
    fake = FakeHAClient(devices=[], areas=[], entities=[])
    cache = EntityRegistryCache(fake, area_lookup=lambda: {}, device_lookup=lambda _: None)
    await cache.load()
    assert cache.entity("light.nope") is None


@pytest.mark.asyncio
async def test_refresh_computes_diff_add_remove_update():
    fake = FakeHAClient(
        devices=[],
        areas=[],
        entities=[
            _ent("light.a", device_id=None, unique_id="a"),
            _ent("light.b", device_id=None, unique_id="b"),
        ],
    )
    cache = EntityRegistryCache(fake, area_lookup=lambda: {}, device_lookup=lambda _: None)
    await cache.load()

    # Mutate: rename light.b, add light.c, remove light.a.
    fake.set_entities([
        {**_ent("light.b", device_id=None, unique_id="b"), "name": "B Renamed"},
        _ent("light.c", device_id=None, unique_id="c"),
    ])
    diff = await cache.refresh()

    assert diff.added == ["light.c"]
    assert diff.removed == ["light.a"]
    assert diff.updated == ["light.b"]
