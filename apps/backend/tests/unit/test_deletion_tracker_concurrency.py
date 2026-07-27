"""`DeletionTracker` state is read from a different thread than it is written.

`all_state()` / `all_entity_state()` are called from `list_devices` and the
policy simulator, which are sync `def` handlers and therefore run in
FastAPI's threadpool. The dicts they iterate are written by
`handle_diff_from_cache()`, which runs on the event loop via the HA event
callbacks. Iterating a dict while another thread inserts into it raises
`RuntimeError: dictionary changed size during iteration` and fails the
request.
"""

import sys
import threading

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from home_curator.deletion_tracker import DeletionTracker
from home_curator.ha_client.fake import FakeHAClient
from home_curator.registry_cache.cache import RegistryCache
from home_curator.storage.models import Base

_WRITES = 4_000
# Enough entries that a snapshot takes long enough to be preempted part-way.
_SEED = 12_000


@pytest.fixture
def fine_grained_switching():
    """Force frequent thread switches so the race is actually exercised.

    At CPython's default 5ms switch interval the snapshot comprehension
    usually finishes within a single time slice, so the unguarded version
    passes by luck — which it did on the first attempt at this test.
    """
    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        yield
    finally:
        sys.setswitchinterval(previous)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as s:
            yield s
    finally:
        engine.dispose()


async def _tracker(session: Session) -> DeletionTracker:
    cache = RegistryCache(FakeHAClient(devices=[], areas=[]))
    await cache.load()
    return DeletionTracker(cache=cache, session=session)


def _hammer(read, write) -> list[BaseException]:
    """Run reader and writer concurrently, collecting anything either raises."""
    failures: list[BaseException] = []
    stop = threading.Event()

    def reader() -> None:
        try:
            while not stop.is_set():
                read()
        except BaseException as exc:  # noqa: BLE001 - reported, not swallowed
            failures.append(exc)
            stop.set()

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    try:
        for i in range(_WRITES):
            if stop.is_set():
                break
            write(i)
    finally:
        stop.set()
        thread.join(timeout=10)
    return failures


@pytest.mark.asyncio
async def test_all_state_survives_concurrent_writes(session, fine_grained_switching):
    tracker = await _tracker(session)
    tracker._state.update({f"seed{i}": {"reappeared": True} for i in range(_SEED)})

    def write(i: int) -> None:
        # Takes the lock exactly as `handle_diff_from_cache` does. The point
        # under test is the reader: if the snapshot did not lock, this would
        # still race no matter how careful the writer was.
        with tracker._lock:
            tracker._state[f"d{i}"] = {"reappeared": True}

    failures = _hammer(read=tracker.all_state, write=write)

    assert not failures, f"all_state() raced with a concurrent write: {failures[0]!r}"


@pytest.mark.asyncio
async def test_all_entity_state_survives_concurrent_writes(
    session, fine_grained_switching
):
    tracker = await _tracker(session)
    tracker._entity_state.update(
        {f"light.seed{i}": {"reappeared": True} for i in range(_SEED)}
    )

    def write(i: int) -> None:
        with tracker._lock:
            tracker._entity_state[f"light.e{i}"] = {"reappeared": True}

    failures = _hammer(read=tracker.all_entity_state, write=write)

    assert not failures, (
        f"all_entity_state() raced with a concurrent write: {failures[0]!r}"
    )


@pytest.mark.asyncio
async def test_state_snapshots_are_independent_copies(session):
    """Callers must not be able to mutate the tracker through what they read."""
    tracker = await _tracker(session)
    tracker._state["d1"] = {"reappeared": True}

    snapshot = tracker.all_state()
    snapshot["d1"]["reappeared"] = False
    snapshot["d2"] = {}

    assert tracker.all_state() == {"d1": {"reappeared": True}}
