"""Startup that fails part-way must still release what it acquired.

Teardown used to be written twice — once in an `except BaseException` for a
failed startup, once in a `finally` for normal shutdown — and the two had
drifted: the failure path closed the database session *before* stopping the
Home Assistant client, whose event callbacks write through that session. One
`AsyncExitStack` now owns it, so both paths are the same code.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from home_curator.config import Settings
from home_curator.main import create_app
from home_curator.storage.models import Base


@pytest.fixture
def settings(tmp_path, monkeypatch) -> Settings:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    engine = create_engine(f"sqlite:///{tmp_path / 'curator.db'}")
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()
    monkeypatch.setenv("HA_TOKEN", "devtoken")
    return Settings(CONFIG_DIR=config_dir, DATA_DIR=tmp_path, HA_TOKEN="devtoken")


def test_client_is_stopped_when_startup_fails(settings, fake_ha, monkeypatch):
    """A failure after `client.start()` must not leave the client running."""
    from home_curator.registry_cache.cache import RegistryCache

    async def explode(self) -> None:
        raise RuntimeError("registry load failed")

    monkeypatch.setattr(RegistryCache, "load", explode)

    stopped: list[bool] = []
    original_stop = fake_ha.stop

    async def record_stop() -> None:
        stopped.append(True)
        await original_stop()

    monkeypatch.setattr(fake_ha, "stop", record_stop)

    app = create_app(ha_client=fake_ha, settings=settings)

    with pytest.raises(RuntimeError, match="registry load failed"):
        with TestClient(app):
            pass

    assert stopped, "the HA client was left running after a failed startup"


def test_client_is_stopped_on_normal_shutdown(settings, fake_ha, monkeypatch):
    stopped: list[bool] = []
    original_stop = fake_ha.stop

    async def record_stop() -> None:
        stopped.append(True)
        await original_stop()

    monkeypatch.setattr(fake_ha, "stop", record_stop)

    app = create_app(ha_client=fake_ha, settings=settings)
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200

    assert stopped


def test_a_failed_startup_still_subscribes_nothing(settings, fake_ha, monkeypatch):
    """The event subscription must not outlive a failed startup either."""
    from home_curator.registry_cache.entity_cache import EntityRegistryCache

    async def explode(self) -> None:
        raise RuntimeError("entity load failed")

    monkeypatch.setattr(EntityRegistryCache, "load", explode)

    app = create_app(ha_client=fake_ha, settings=settings)
    with pytest.raises(RuntimeError, match="entity load failed"):
        with TestClient(app):
            pass

    # `subscribe` returns an unsubscribe callable that the stack invokes; if it
    # were skipped the fake would still be holding a handler.
    assert fake_ha._handlers == []
