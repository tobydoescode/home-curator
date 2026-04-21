import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from home_curator.storage.exceptions_repo import ExceptionsRepo
from home_curator.storage.models import Base


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_acknowledge_and_list(session):
    repo = ExceptionsRepo(session)
    repo.acknowledge("dev1", "pol1", note="known good")
    session.commit()
    all_for_device = repo.for_device("dev1")
    assert len(all_for_device) == 1
    assert all_for_device[0].policy_id == "pol1"
    assert all_for_device[0].note == "known good"


def test_acknowledge_is_idempotent(session):
    repo = ExceptionsRepo(session)
    repo.acknowledge("dev1", "pol1")
    repo.acknowledge("dev1", "pol1", note="updated")
    session.commit()
    rows = repo.for_device("dev1")
    assert len(rows) == 1
    assert rows[0].note == "updated"


def test_clear(session):
    repo = ExceptionsRepo(session)
    repo.acknowledge("dev1", "pol1")
    session.commit()
    repo.clear("dev1", "pol1")
    session.commit()
    assert repo.for_device("dev1") == []


def test_is_acknowledged(session):
    repo = ExceptionsRepo(session)
    assert not repo.is_acknowledged("dev1", "pol1")
    repo.acknowledge("dev1", "pol1")
    session.commit()
    assert repo.is_acknowledged("dev1", "pol1")
