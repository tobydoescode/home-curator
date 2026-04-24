from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from home_curator.storage.deletion_repo import DeletionRepo, identifiers_hash
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


def test_identifiers_hash_is_order_independent():
    a = identifiers_hash([("hue", "x"), ("zigbee", "y")])
    b = identifiers_hash([("zigbee", "y"), ("hue", "x")])
    assert a == b


def test_record_and_find_reappearance(session):
    repo = DeletionRepo(session)
    h = identifiers_hash([("hue", "abc")])
    assert repo.is_reappearance(h) is False
    repo.record_deletion(
        device_id="dev-old",
        id_hash=h,
        first_seen_at=datetime.now(UTC) - timedelta(days=3),
        deleted_at=datetime.now(UTC),
    )
    session.commit()
    assert repo.is_reappearance(h) is True


def test_mark_reappeared(session):
    repo = DeletionRepo(session)
    h = identifiers_hash([("hue", "abc")])
    repo.record_deletion("dev-old", h, datetime.now(UTC), datetime.now(UTC))
    session.commit()
    repo.mark_reappeared(h)
    session.commit()
    events = repo.events_for_hash(h)
    assert events[0].reappeared_at is not None


def test_mark_reappeared_updates_identity_map(session):
    """Loaded DeletionEvent instances see reappeared_at without an expire."""
    repo = DeletionRepo(session)
    h = identifiers_hash([("hue", "abc")])
    repo.record_deletion("dev-old", h, datetime.now(UTC), datetime.now(UTC))
    session.commit()
    loaded = repo.events_for_hash(h)[0]
    assert loaded.reappeared_at is None
    repo.mark_reappeared(h)
    assert loaded.reappeared_at is not None


def test_all_reappeared_hashes_empty(session):
    assert DeletionRepo(session).all_reappeared_hashes() == set()


def test_all_reappeared_hashes_returns_only_reappeared(session):
    repo = DeletionRepo(session)
    h1 = identifiers_hash([("hue", "1")])
    h2 = identifiers_hash([("hue", "2")])
    now = datetime.now(UTC)
    repo.record_deletion("d1", h1, now, now)
    repo.record_deletion("d2", h2, now, now)
    session.commit()
    repo.mark_reappeared(h1)
    session.commit()
    assert repo.all_reappeared_hashes() == {h1}


def test_all_reappeared_hashes_deduplicates(session):
    repo = DeletionRepo(session)
    h = identifiers_hash([("hue", "1")])
    now = datetime.now(UTC)
    repo.record_deletion("d1", h, now, now)
    session.commit()
    repo.mark_reappeared(h)
    session.commit()
    repo.record_deletion("d1", h, now, now)
    session.commit()
    repo.mark_reappeared(h)
    session.commit()
    assert repo.all_reappeared_hashes() == {h}
