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


def test_acknowledged_by_is_stored_and_updated(session):
    repo = ExceptionsRepo(session)
    repo.acknowledge("dev1", "pol1", note="first", acknowledged_by="alice")
    session.commit()
    row = repo.for_device("dev1")[0]
    assert row.acknowledged_by == "alice"

    repo.acknowledge("dev1", "pol1", note="second", acknowledged_by="bob")
    session.commit()
    row = repo.for_device("dev1")[0]
    assert row.acknowledged_by == "bob"


def test_for_device_isolates_by_device(session):
    repo = ExceptionsRepo(session)
    repo.acknowledge("dev1", "pol1")
    repo.acknowledge("dev2", "pol2")
    session.commit()
    assert [r.policy_id for r in repo.for_device("dev1")] == ["pol1"]
    assert [r.policy_id for r in repo.for_device("dev2")] == ["pol2"]


def test_all_acknowledged_keys_empty(session):
    repo = ExceptionsRepo(session)
    assert repo.all_acknowledged_keys() == set()


def test_all_acknowledged_keys_returns_all_pairs(session):
    repo = ExceptionsRepo(session)
    repo.acknowledge("d1", "p1")
    repo.acknowledge("d1", "p2")
    repo.acknowledge("d2", "p1")
    session.commit()
    assert repo.all_acknowledged_keys() == {("d1", "p1"), ("d1", "p2"), ("d2", "p1")}


def test_all_acknowledged_keys_reflects_clear(session):
    repo = ExceptionsRepo(session)
    repo.acknowledge("d1", "p1")
    repo.acknowledge("d1", "p2")
    session.commit()
    repo.clear("d1", "p1")
    session.commit()
    assert repo.all_acknowledged_keys() == {("d1", "p2")}


from datetime import UTC, datetime

from home_curator.storage.db import session_scope
from home_curator.storage.models import Exemption


def test_list_paginated_orders_newest_first(session_factory):
    with session_scope(session_factory) as s:
        s.add(Exemption(device_id="d1", policy_id="p1", acknowledged_at=datetime(2026, 1, 1, tzinfo=UTC)))
        s.add(Exemption(device_id="d2", policy_id="p1", acknowledged_at=datetime(2026, 2, 1, tzinfo=UTC)))
        s.add(Exemption(device_id="d3", policy_id="p2", acknowledged_at=datetime(2026, 3, 1, tzinfo=UTC)))
    with session_scope(session_factory) as s:
        rows, total = ExceptionsRepo(s).list_paginated(page=1, page_size=2)
    assert total == 3
    assert [r.device_id for r in rows] == ["d3", "d2"]


def test_list_paginated_filters_by_policy_and_device(session_factory):
    with session_scope(session_factory) as s:
        s.add(Exemption(device_id="d1", policy_id="p1"))
        s.add(Exemption(device_id="d2", policy_id="p2"))
    with session_scope(session_factory) as s:
        rows, _ = ExceptionsRepo(s).list_paginated(policy_ids={"p1"})
    assert [r.device_id for r in rows] == ["d1"]


def test_bulk_delete_returns_deleted_count(session_factory):
    with session_scope(session_factory) as s:
        s.add_all([
            Exemption(id=1, device_id="d1", policy_id="p1"),
            Exemption(id=2, device_id="d2", policy_id="p1"),
            Exemption(id=3, device_id="d3", policy_id="p1"),
        ])
    with session_scope(session_factory) as s:
        deleted = ExceptionsRepo(s).bulk_delete({1, 3})
    assert deleted == 2
    with session_scope(session_factory) as s:
        rows, total = ExceptionsRepo(s).list_paginated()
        assert total == 1 and rows[0].id == 2
