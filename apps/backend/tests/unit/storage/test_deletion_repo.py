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
    with Session(engine) as s:
        yield s


def test_identifiers_hash_is_order_independent():
    a = identifiers_hash([("hue", "x"), ("zigbee", "y")])
    b = identifiers_hash([("zigbee", "y"), ("hue", "x")])
    assert a == b


def test_record_and_find_reappearance(session):
    repo = DeletionRepo(session)
    h = identifiers_hash([("hue", "abc")])
    # Initially none known
    assert repo.is_reappearance(h) is False
    # Record a deletion
    repo.record_deletion(
        device_id="dev-old",
        identifiers_hash=h,
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
