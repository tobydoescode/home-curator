"""The ORM models and the Alembic migrations must describe the same schema.

Tests build their schema with `Base.metadata.create_all()`; production builds
it with `alembic upgrade head`. Nothing compared the two, so they were free to
diverge — and had: the partial unique index on `exceptions` was created by raw
SQL inside `0002_entity_support` and never declared on the model, so every
test ran against a schema missing a constraint that production has. An upsert
targeting that index worked in production and failed in tests.
"""

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command
from home_curator.storage.models import Base

_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _alembic_config(url: str) -> Config:
    cfg = Config(str(_BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    cfg.set_main_option("script_location", str(_BACKEND_ROOT / "alembic"))
    return cfg


def _schema_from_migrations(tmp_path: Path) -> dict[str, dict[str, object]]:
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    command.upgrade(_alembic_config(url), "head")
    return _describe(url)


def _schema_from_models(tmp_path: Path) -> dict[str, dict[str, object]]:
    url = f"sqlite:///{tmp_path / 'created.db'}"
    engine = create_engine(url)
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()
    return _describe(url)


def _describe(url: str) -> dict[str, dict[str, object]]:
    """Tables, columns and index SQL, in a form that compares cleanly."""
    engine = create_engine(url)
    try:
        insp = inspect(engine)
        out: dict[str, dict[str, object]] = {}
        for table in sorted(insp.get_table_names()):
            if table == "alembic_version":
                continue
            out[table] = {
                "columns": sorted(
                    (c["name"], str(c["type"]).upper(), bool(c["nullable"]))
                    for c in insp.get_columns(table)
                ),
                # Reflection skips expression-based indexes, so index *names*
                # are compared rather than their definitions. That is enough
                # to catch one side having an index the other lacks.
                "indexes": sorted(i["name"] or "" for i in insp.get_indexes(table)),
            }
        return out
    finally:
        engine.dispose()


@pytest.fixture
def migrated(tmp_path):
    return _schema_from_migrations(tmp_path / "a")


@pytest.fixture
def created(tmp_path):
    return _schema_from_models(tmp_path / "b")


@pytest.fixture(autouse=True)
def _dirs(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()


def test_the_same_tables_exist(migrated, created):
    assert sorted(migrated) == sorted(created)


def test_every_table_has_the_same_columns(migrated, created):
    for table in sorted(migrated):
        assert migrated[table]["columns"] == created[table]["columns"], (
            f"{table} differs between the migrations and the models"
        )


def test_every_table_has_the_same_indexes(migrated, created):
    """The check that would have caught `ix_exceptions_target_policy`."""
    for table in sorted(migrated):
        assert migrated[table]["indexes"] == created[table]["indexes"], (
            f"{table} indexes differ between the migrations and the models"
        )


def test_expression_index_on_exceptions_exists_in_both(tmp_path):
    """Reflection skips expression indexes, so assert on the raw SQL.

    This is the constraint that stops one target being acknowledged twice for
    the same policy.
    """
    from sqlalchemy import text

    found = {}
    for label, build in (
        ("migrations", _schema_from_migrations),
        ("models", _schema_from_models),
    ):
        directory = tmp_path / label
        directory.mkdir()
        build(directory)
        db = next(directory.glob("*.db"))
        engine = create_engine(f"sqlite:///{db}")
        try:
            with engine.connect() as conn:
                rows = conn.execute(
                    text(
                        "SELECT sql FROM sqlite_master WHERE type='index' "
                        "AND name='ix_exceptions_target_policy'"
                    )
                ).fetchall()
        finally:
            engine.dispose()
        assert rows, f"index missing from the {label} schema"
        found[label] = rows[0][0].lower().replace('"', "").replace(" ", "")

    assert found["migrations"] == found["models"]
