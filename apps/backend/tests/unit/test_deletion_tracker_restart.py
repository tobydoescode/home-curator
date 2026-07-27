"""Reappearance survives a restart.

`reappeared_after_delete` fires off `DeletionTracker`'s in-memory state. That
state was only ever populated by observing the transition live, so restarting
the addon silently cleared every reappearance flag — and because
`is_reappearance` had already stamped `reappeared_at`, the transition could
never be observed again either. The issue simply vanished, with no user
action and nothing to explain it.

The database has known the answer the whole time:
`DeletionRepo.all_reappeared_hashes()` existed, was tested, and was never
called by anything.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from home_curator.deletion_tracker import DeletionTracker
from home_curator.ha_client.fake import FakeHAClient
from home_curator.ha_client.models import HADevice, HAEntity
from home_curator.registry_cache.cache import RegistryCache
from home_curator.registry_cache.entity_cache import EntityRegistryCache
from home_curator.rules.reappeared_after_delete import STATE_KEY_REAPPEARED
from home_curator.storage.models import Base


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as s:
            yield s
    finally:
        engine.dispose()


def _dev(id_: str, identifiers: list[list[str]]) -> HADevice:
    return HADevice(
        id=id_,
        name=id_,
        name_by_user=None,
        manufacturer=None,
        model=None,
        area_id=None,
        integration=None,
        disabled_by=None,
        identifiers=identifiers,
        entities=[],
    )


def _ent(entity_id: str, unique_id: str) -> HAEntity:
    return HAEntity(
        entity_id=entity_id,
        name=None,
        original_name=None,
        icon=None,
        platform="hue",
        device_id=None,
        area_id=None,
        disabled_by=None,
        hidden_by=None,
        unique_id=unique_id,
    )


async def _cache(fake: FakeHAClient) -> RegistryCache:
    cache = RegistryCache(fake)
    await cache.load()
    return cache


@pytest.mark.asyncio
async def test_device_reappearance_survives_a_restart(session):
    fake = FakeHAClient(devices=[_dev("d1", [["hue", "abc"]])], areas=[])
    cache = await _cache(fake)
    tracker = DeletionTracker(cache=cache, session=session)

    # Gone…
    fake.set_devices([])
    await cache.refresh()
    tracker.handle_diff_from_cache()

    # …and back.
    fake.set_devices([_dev("d1", [["hue", "abc"]])])
    await cache.refresh()
    tracker.handle_diff_from_cache()
    session.commit()
    assert tracker.all_state()["d1"][STATE_KEY_REAPPEARED] is True

    # Restart: same database, same registry, brand new tracker.
    restarted = DeletionTracker(cache=cache, session=session)

    assert restarted.all_state().get("d1", {}).get(STATE_KEY_REAPPEARED) is True


@pytest.mark.asyncio
async def test_entity_reappearance_survives_a_restart(session):
    entity = _ent("light.lamp", "hue-1")
    fake = FakeHAClient(devices=[], areas=[], entities=[entity])
    cache = await _cache(fake)
    entity_cache = EntityRegistryCache(
        fake, area_lookup=cache.area_id_to_name, device_lookup=cache.device
    )
    await entity_cache.load()
    tracker = DeletionTracker(
        cache=cache, session=session, entity_cache=entity_cache
    )

    fake.set_entities([])
    await entity_cache.refresh()
    tracker.handle_entity_diff_from_cache()

    fake.set_entities([entity])
    await entity_cache.refresh()
    tracker.handle_entity_diff_from_cache()
    session.commit()
    assert tracker.all_entity_state()["light.lamp"][STATE_KEY_REAPPEARED] is True

    restarted = DeletionTracker(
        cache=cache, session=session, entity_cache=entity_cache
    )

    assert (
        restarted.all_entity_state().get("light.lamp", {}).get(STATE_KEY_REAPPEARED)
        is True
    )


@pytest.mark.asyncio
async def test_a_device_that_never_vanished_is_not_marked(session):
    fake = FakeHAClient(devices=[_dev("d1", [["hue", "abc"]])], areas=[])
    cache = await _cache(fake)

    tracker = DeletionTracker(cache=cache, session=session)

    assert tracker.all_state() == {}


@pytest.mark.asyncio
async def test_a_deletion_not_yet_followed_by_a_return_is_not_marked(session):
    """Only a *completed* delete-then-return counts."""
    fake = FakeHAClient(devices=[_dev("d1", [["hue", "abc"]])], areas=[])
    cache = await _cache(fake)
    tracker = DeletionTracker(cache=cache, session=session)

    fake.set_devices([])
    await cache.refresh()
    tracker.handle_diff_from_cache()
    session.commit()

    restarted = DeletionTracker(cache=cache, session=session)

    assert restarted.all_state() == {}
