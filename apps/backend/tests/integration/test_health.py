from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from home_curator.main import create_app
from home_curator.storage.models import Base


def test_health_endpoint(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


class LifecycleClient:
    def __init__(self):
        self.started = False
        self.stopped = False
        self.unsubscribed = False
        self.handlers = []

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True

    async def get_devices(self):
        return []

    async def get_entities(self):
        return []

    async def get_areas(self):
        return []

    def subscribe(self, handler):
        self.handlers.append(handler)

        def unsubscribe():
            self.unsubscribed = True

        return unsubscribe


def test_create_app_lifespan_starts_and_stops_client(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "policies.yaml").write_text("version: 1\npolicies: []\n")
    monkeypatch.setenv("CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HA_TOKEN", "devtoken")
    engine = create_engine(f"sqlite:///{tmp_path / 'curator.db'}")
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()
    client = LifecycleClient()
    app = create_app(ha_client=client)

    with TestClient(app) as tc:
        assert tc.get("/api/health").json() == {"ok": True}
        assert client.started is True
        assert len(client.handlers) == 1

    assert client.unsubscribed is True
    assert client.stopped is True
