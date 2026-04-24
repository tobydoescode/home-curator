import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from home_curator.storage.exceptions_repo import ExceptionsRepo
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


def test_ack_entity_then_list(session):
    repo = ExceptionsRepo(session)
    repo.ack_entity("light.lamp", "entity-naming", note="seeded by integration")
    session.commit()
    rows = repo.for_entity("light.lamp")
    assert len(rows) == 1
    assert rows[0].entity_id == "light.lamp"
    assert rows[0].device_id is None
    assert rows[0].note == "seeded by integration"


def test_ack_entity_is_idempotent(session):
    repo = ExceptionsRepo(session)
    repo.ack_entity("light.lamp", "p1", note="first")
    repo.ack_entity("light.lamp", "p1", note="second")
    session.commit()
    rows = repo.for_entity("light.lamp")
    assert len(rows) == 1
    assert rows[0].note == "second"


def test_clear_entity(session):
    repo = ExceptionsRepo(session)
    repo.ack_entity("light.lamp", "p1")
    session.commit()
    repo.clear_entity("light.lamp", "p1")
    session.commit()
    assert repo.for_entity("light.lamp") == []


def test_all_acknowledged_keys_mixes_kinds(session):
    repo = ExceptionsRepo(session)
    repo.acknowledge("d1", "p1")
    repo.ack_entity("light.lamp", "p1")
    session.commit()
    assert repo.all_acknowledged_keys() == {
        ("device", "d1", "p1"),
        ("entity", "light.lamp", "p1"),
    }


def test_list_all_returns_both_kinds_newest_first(session):
    repo = ExceptionsRepo(session)
    repo.acknowledge("d1", "p1")
    session.commit()
    repo.ack_entity("light.lamp", "p1")
    session.commit()
    rows = repo.list_all()
    # newest first: the entity ack was written second
    assert rows[0].entity_id == "light.lamp"
    assert rows[1].device_id == "d1"


def test_device_and_entity_with_same_surface_id_and_policy_coexist(session):
    """A device_id and an entity_id can (in principle) share characters.
    The kind discriminator + exactly-one-of constraint keep them distinct
    rows — neither conflicts on insert."""
    repo = ExceptionsRepo(session)
    repo.acknowledge("light.lamp", "p1")
    repo.ack_entity("light.lamp", "p1")
    session.commit()
    rows = repo.list_all()
    assert len(rows) == 2
    kinds = {("device" if r.device_id else "entity") for r in rows}
    assert kinds == {"device", "entity"}
