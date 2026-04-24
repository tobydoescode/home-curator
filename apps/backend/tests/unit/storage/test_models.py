from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from home_curator.storage.models import Base, DeletionEvent, EntityRole, Exemption


def _engine():
    e = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(e)
    return e


def test_exemption_roundtrip():
    engine = _engine()
    try:
        with Session(engine) as s:
            s.add(Exemption(device_id="dev1", policy_id="pol1", note="known good"))
            s.commit()
            row = s.query(Exemption).one()
            assert row.device_id == "dev1"
            assert row.policy_id == "pol1"
            assert row.note == "known good"
            assert row.acknowledged_by is None
            assert row.acknowledged_at is not None
            # TZDateTime preserves UTC tzinfo through the roundtrip
            assert row.acknowledged_at.tzinfo == UTC
    finally:
        engine.dispose()


def test_deletion_event_roundtrip():
    engine = _engine()
    now = datetime.now(UTC)
    try:
        with Session(engine) as s:
            s.add(
                DeletionEvent(
                    device_id="dev2",
                    identifiers_hash="abcd",
                    first_seen_at=now,
                    deleted_at=now,
                )
            )
            s.commit()
            row = s.query(DeletionEvent).one()
            assert row.device_id == "dev2"
            assert row.identifiers_hash == "abcd"
            assert row.first_seen_at.tzinfo == UTC
            assert row.deleted_at.tzinfo == UTC
            assert row.reappeared_at is None
    finally:
        engine.dispose()


def test_entity_role_roundtrip():
    engine = _engine()
    try:
        with Session(engine) as s:
            s.add(EntityRole(device_id="dev3", role="battery", entity_id="sensor.bat"))
            s.commit()
            row = s.query(EntityRole).one()
            assert row.device_id == "dev3"
            assert row.role == "battery"
            assert row.entity_id == "sensor.bat"
    finally:
        engine.dispose()


def test_entity_role_enum_rejects_invalid_role():
    import pytest
    from sqlalchemy.exc import StatementError

    engine = _engine()
    try:
        with Session(engine) as s:
            s.add(EntityRole(device_id="dev4", role="invalid_role", entity_id="x"))  # type: ignore[arg-type]
            with pytest.raises((StatementError, Exception)):
                s.commit()
    finally:
        engine.dispose()
