import sqlite3
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command


def _alembic_config(db_url: str) -> Config:
    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.set_main_option("script_location", str(root / "alembic"))
    return cfg


def test_fresh_db_upgrades_to_head(tmp_path):
    db = tmp_path / "curator.db"
    url = f"sqlite:///{db}"
    command.upgrade(_alembic_config(url), "head")

    engine = create_engine(url)
    try:
        insp = inspect(engine)
        exc_cols = {c["name"] for c in insp.get_columns("exceptions")}
        assert "device_id" in exc_cols
        assert "entity_id" in exc_cols
        del_cols = {c["name"] for c in insp.get_columns("deletion_events")}
        assert "entity_id" in del_cols
        assert "platform" in del_cols
    finally:
        engine.dispose()

    # CHECK constraint enforces exactly-one on exceptions.
    with sqlite3.connect(str(db)) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO exceptions(device_id, entity_id, policy_id, acknowledged_at) "
                "VALUES ('d1', 'light.lamp', 'p1', '2026-01-01T00:00:00+00:00')"
            )
            conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO exceptions(device_id, entity_id, policy_id, acknowledged_at) "
                "VALUES (NULL, NULL, 'p1', '2026-01-01T00:00:00+00:00')"
            )
            conn.commit()


def test_upgrade_preserves_device_only_rows(tmp_path):
    """Simulate upgrading a DB that was stamped at revision 0001 with
    device-only rows. After upgrade they survive with entity_id=NULL."""
    db = tmp_path / "curator.db"
    url = f"sqlite:///{db}"

    # Stamp at 0001 and insert one device row shaped per the old schema.
    command.upgrade(_alembic_config(url), "0001")
    with sqlite3.connect(str(db)) as conn:
        conn.execute(
            "INSERT INTO exceptions(device_id, policy_id, acknowledged_at) "
            "VALUES ('d1', 'p1', '2026-01-01T00:00:00+00:00')"
        )
        conn.execute(
            "INSERT INTO deletion_events(device_id, identifiers_hash, first_seen_at, deleted_at) "
            "VALUES ('d2', 'hhh', '2026-01-01T00:00:00+00:00', '2026-01-02T00:00:00+00:00')"
        )
        conn.commit()

    command.upgrade(_alembic_config(url), "head")
    with sqlite3.connect(str(db)) as conn:
        exc = conn.execute(
            "SELECT device_id, entity_id, policy_id FROM exceptions"
        ).fetchall()
        de = conn.execute(
            "SELECT device_id, entity_id, platform FROM deletion_events"
        ).fetchall()
    assert exc == [("d1", None, "p1")]
    assert de == [("d2", None, None)]
