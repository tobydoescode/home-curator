from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from home_curator.config import Settings
from home_curator.ha_client.fake import FakeHAClient
from home_curator.main import create_app
from home_curator.storage.models import Base


def _seed_db(path: Path):
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)


@pytest.fixture
def fake_ha():
    return FakeHAClient(
        devices=[
            {
                "id": "d1",
                "name": "living_room_lamp",
                "name_by_user": None,
                "manufacturer": "Signify",
                "model": "m",
                "area_id": "living",
                "integration": "hue",
                "disabled_by": None,
                "identifiers": [["hue", "a"]],
                "config_entries": ["e1"],
                "entities": [{"id": "light.lamp", "domain": "light"}],
            },
            {
                "id": "d2",
                "name": "BadCase",
                "name_by_user": None,
                "manufacturer": "Aqara",
                "model": "m",
                "area_id": None,
                "integration": "aqara",
                "disabled_by": None,
                "identifiers": [["aqara", "b"]],
                "config_entries": ["e2"],
                "entities": [],
            },
        ],
        areas=[{"id": "living", "name": "Living Room"}],
    )


@pytest.fixture
def app_with_fake(tmp_path, fake_ha, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    policies = config_dir / "policies.yaml"
    policies.write_text(
        """
version: 1
policies:
  - id: missing-room
    type: missing_area
    enabled: true
    severity: warning
  - id: naming-convention
    type: naming_convention
    enabled: true
    severity: warning
    global:
      preset: snake_case
    rooms: []
""".strip()
    )
    _seed_db(tmp_path / "curator.db")
    monkeypatch.setenv("CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HA_TOKEN", "devtoken")
    app = create_app(ha_client=fake_ha, settings=Settings())
    return app


@pytest.fixture
def client(app_with_fake):
    with TestClient(app_with_fake) as c:
        yield c
