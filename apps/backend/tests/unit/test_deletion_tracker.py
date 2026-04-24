import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from home_curator.deletion_tracker import DeletionTracker
from home_curator.ha_client.fake import FakeHAClient
from home_curator.ha_client.models import HADevice
from home_curator.registry_cache.cache import RegistryCache
from home_curator.storage.deletion_repo import DeletionRepo, identifiers_hash
from home_curator.storage.models import Base


def _session():
    e = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(e)
    return Session(e)


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


@pytest.mark.asyncio
async def test_deletion_recorded_on_disappearance():
    fake = FakeHAClient(devices=[_dev("d1", [["hue", "abc"]])], areas=[])
    cache = RegistryCache(fake)
    await cache.load()
    session = _session()
    tracker = DeletionTracker(cache=cache, session=session)

    fake.set_devices([])
    await cache.refresh()
    tracker.handle_diff_from_cache()

    session.commit()
    h = identifiers_hash([("hue", "abc")])
    assert DeletionRepo(session).is_reappearance(h)


@pytest.mark.asyncio
async def test_reappearance_marked_and_state_flag_set():
    fake = FakeHAClient(devices=[_dev("d1", [["hue", "abc"]])], areas=[])
    cache = RegistryCache(fake)
    await cache.load()
    session = _session()
    tracker = DeletionTracker(cache=cache, session=session)

    # Delete
    fake.set_devices([])
    await cache.refresh()
    tracker.handle_diff_from_cache()
    session.commit()

    # Re-add with SAME identifiers but NEW internal id
    fake.set_devices([_dev("d2", [["hue", "abc"]])])
    await cache.refresh()
    tracker.handle_diff_from_cache()
    session.commit()

    # Reappearance should be tracked and the flag should be set in state
    assert tracker.state_for("d2").get("reappeared_after_delete") is True


@pytest.mark.asyncio
async def test_state_and_snapshots_pruned_on_delete():
    """Reappeared device that's later deleted doesn't leak state."""
    fake = FakeHAClient(devices=[_dev("d1", [["hue", "abc"]])], areas=[])
    cache = RegistryCache(fake)
    await cache.load()
    session = _session()
    tracker = DeletionTracker(cache=cache, session=session)

    # Delete + re-add to set reappeared flag on d2
    fake.set_devices([])
    await cache.refresh()
    tracker.handle_diff_from_cache()
    session.commit()

    fake.set_devices([_dev("d2", [["hue", "abc"]])])
    await cache.refresh()
    tracker.handle_diff_from_cache()
    session.commit()
    assert "d2" in tracker.all_state()

    # Delete d2; state and snapshots prune out
    fake.set_devices([])
    await cache.refresh()
    tracker.handle_diff_from_cache()
    session.commit()
    assert "d2" not in tracker.all_state()
    assert tracker._last_known_identifiers == {}
    assert tracker._last_known_first_seen == {}
