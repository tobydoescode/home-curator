from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from home_curator.storage.models import Base, DeletionEvent, Exception_, EntityRole


def _engine():
    e = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(e)
    return e


def test_exception_roundtrip():
    engine = _engine()
    with Session(engine) as s:
        s.add(Exception_(device_id="dev1", policy_id="pol1", note="known good"))
        s.commit()
        row = s.query(Exception_).one()
        assert row.device_id == "dev1"
        assert row.policy_id == "pol1"
        assert row.note == "known good"
        assert row.acknowledged_at is not None


def test_deletion_event_roundtrip():
    engine = _engine()
    with Session(engine) as s:
        s.add(
            DeletionEvent(
                device_id="dev2",
                identifiers_hash="abcd",
                first_seen_at=datetime.now(UTC),
                deleted_at=datetime.now(UTC),
            )
        )
        s.commit()
        row = s.query(DeletionEvent).one()
        assert row.reappeared_at is None


def test_entity_role_roundtrip():
    engine = _engine()
    with Session(engine) as s:
        s.add(EntityRole(device_id="dev3", role="battery", entity_id="sensor.bat"))
        s.commit()
        assert s.query(EntityRole).count() == 1
