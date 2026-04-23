import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from home_curator.deletion_tracker import DeletionTracker
from home_curator.ha_client.base import HAEntityDict
from home_curator.ha_client.fake import FakeHAClient
from home_curator.registry_cache.cache import RegistryCache
from home_curator.registry_cache.entity_cache import EntityRegistryCache
from home_curator.storage.deletion_repo import DeletionRepo, identifiers_hash
from home_curator.storage.models import Base


def _session():
    e = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(e)
    return Session(e)


def _ent(
    eid: str,
    platform: str = "hue",
    unique_id: str | None = "u1",
    device_id: str | None = None,
) -> HAEntityDict:
    return {
        "entity_id": eid,
        "name": None,
        "original_name": eid,
        "platform": platform,
        "device_id": device_id,
        "area_id": None,
        "disabled_by": None,
        "hidden_by": None,
        "unique_id": unique_id,
    }


@pytest.mark.asyncio
async def test_entity_deletion_recorded_on_disappearance():
    fake = FakeHAClient(devices=[], areas=[], entities=[_ent("light.a", unique_id="u1")])
    dev_cache = RegistryCache(fake)
    await dev_cache.load()
    ent_cache = EntityRegistryCache(
        fake,
        area_lookup=dev_cache.area_id_to_name,
        device_lookup=dev_cache.device,
    )
    await ent_cache.load()
    session = _session()
    tracker = DeletionTracker(cache=dev_cache, session=session, entity_cache=ent_cache)

    fake.set_entities([])
    await ent_cache.refresh()
    tracker.handle_entity_diff_from_cache()
    session.commit()

    h = identifiers_hash([("hue", "u1")])
    assert DeletionRepo(session).is_reappearance(h)


@pytest.mark.asyncio
async def test_entity_reappearance_flags_state_under_new_entity_id():
    fake = FakeHAClient(devices=[], areas=[], entities=[_ent("light.a", unique_id="u1")])
    dev_cache = RegistryCache(fake)
    await dev_cache.load()
    ent_cache = EntityRegistryCache(
        fake,
        area_lookup=dev_cache.area_id_to_name,
        device_lookup=dev_cache.device,
    )
    await ent_cache.load()
    session = _session()
    tracker = DeletionTracker(cache=dev_cache, session=session, entity_cache=ent_cache)

    fake.set_entities([])
    await ent_cache.refresh()
    tracker.handle_entity_diff_from_cache()
    session.commit()

    # Re-add with the SAME platform+unique_id but a NEW entity_id.
    fake.set_entities([_ent("light.b", unique_id="u1")])
    await ent_cache.refresh()
    tracker.handle_entity_diff_from_cache()
    session.commit()

    assert tracker.entity_state_for("light.b").get("reappeared_after_delete") is True


@pytest.mark.asyncio
async def test_entity_without_unique_id_falls_back_to_entity_id_identity():
    fake = FakeHAClient(
        devices=[], areas=[],
        entities=[_ent("light.a", unique_id=None)],
    )
    dev_cache = RegistryCache(fake)
    await dev_cache.load()
    ent_cache = EntityRegistryCache(
        fake,
        area_lookup=dev_cache.area_id_to_name,
        device_lookup=dev_cache.device,
    )
    await ent_cache.load()
    session = _session()
    tracker = DeletionTracker(cache=dev_cache, session=session, entity_cache=ent_cache)

    fake.set_entities([])
    await ent_cache.refresh()
    tracker.handle_entity_diff_from_cache()
    session.commit()

    fake.set_entities([_ent("light.a", unique_id=None)])
    await ent_cache.refresh()
    tracker.handle_entity_diff_from_cache()
    session.commit()

    # Same entity_id + same platform ⇒ reappearance via the fallback identity.
    assert tracker.entity_state_for("light.a").get("reappeared_after_delete") is True


@pytest.mark.asyncio
async def test_different_platform_is_not_a_reappearance():
    fake = FakeHAClient(
        devices=[], areas=[],
        entities=[_ent("light.a", platform="hue", unique_id="u1")],
    )
    dev_cache = RegistryCache(fake)
    await dev_cache.load()
    ent_cache = EntityRegistryCache(
        fake,
        area_lookup=dev_cache.area_id_to_name,
        device_lookup=dev_cache.device,
    )
    await ent_cache.load()
    session = _session()
    tracker = DeletionTracker(cache=dev_cache, session=session, entity_cache=ent_cache)

    fake.set_entities([])
    await ent_cache.refresh()
    tracker.handle_entity_diff_from_cache()
    session.commit()

    fake.set_entities([_ent("light.a", platform="mqtt", unique_id="u1")])
    await ent_cache.refresh()
    tracker.handle_entity_diff_from_cache()
    session.commit()

    # Different platform ⇒ different identity ⇒ no reappearance.
    assert tracker.entity_state_for("light.a").get("reappeared_after_delete") is not True
