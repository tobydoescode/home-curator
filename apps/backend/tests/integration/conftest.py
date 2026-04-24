from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from home_curator.config import Settings
from home_curator.ha_client.fake import FakeHAClient
from home_curator.ha_client.models import HAArea, HADevice, HADeviceEntityRef, HAEntity
from home_curator.main import create_app
from home_curator.storage.models import Base


def _seed_db(path: Path):
    engine = create_engine(f"sqlite:///{path}")
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()


@pytest.fixture
def fake_ha():
    return FakeHAClient(
        devices=[
            HADevice(
                id="d1",
                name="living_room_lamp",
                name_by_user=None,
                manufacturer="Signify",
                model="m",
                area_id="living",
                integration="hue",
                disabled_by=None,
                identifiers=[["hue", "a"]],
                config_entries=["e1"],
                entities=[HADeviceEntityRef(id="light.lamp", domain="light")],
            ),
            HADevice(
                id="d2",
                name="BadCase",
                name_by_user=None,
                manufacturer="Aqara",
                model="m",
                area_id=None,
                integration="aqara",
                disabled_by=None,
                identifiers=[["aqara", "b"]],
                config_entries=["e2"],
                entities=[],
            ),
        ],
        areas=[
            HAArea(id="living", name="Living Room"),
            HAArea(id="kitchen", name="Kitchen"),
            HAArea(id="garage", name="Garage"),
        ],
        entities=[
            # Owned by d1, living room via device fallback.
            HAEntity(
                entity_id="light.lamp",
                name=None,
                original_name="Living Room Lamp",
                icon=None,
                platform="hue",
                device_id="d1",
                area_id=None,
                disabled_by=None,
                hidden_by=None,
                unique_id="hue-lamp-1",
                created_at="2026-01-01T00:00:00+00:00",
                modified_at="2026-01-01T00:00:00+00:00",
            ),
            # Standalone light in the kitchen; user-renamed.
            HAEntity(
                entity_id="light.kitchen_ceiling",
                name="Kitchen Ceiling",
                original_name="Ceiling Light",
                icon=None,
                platform="mqtt",
                device_id=None,
                area_id="kitchen",
                disabled_by=None,
                hidden_by=None,
                unique_id="mqtt-kc-1",
                created_at="2026-01-02T00:00:00+00:00",
                modified_at="2026-01-02T00:00:00+00:00",
            ),
            # Sensor owned by d2 (no area_id on device), platform=aqara.
            HAEntity(
                entity_id="sensor.temperature",
                name=None,
                original_name="Temperature",
                icon=None,
                platform="aqara",
                device_id="d2",
                area_id=None,
                disabled_by=None,
                hidden_by=None,
                unique_id="aqara-temp-1",
                created_at="2026-01-03T00:00:00+00:00",
                modified_at="2026-01-03T00:00:00+00:00",
            ),
            # Disabled switch in the garage.
            HAEntity(
                entity_id="switch.garage_door",
                name="Garage Door",
                original_name="Switch",
                icon=None,
                platform="zwave_js",
                device_id=None,
                area_id="garage",
                disabled_by="user",
                hidden_by=None,
                unique_id="zwave-gd-1",
                created_at="2026-01-04T00:00:00+00:00",
                modified_at="2026-01-04T00:00:00+00:00",
            ),
            # Hidden binary sensor in the kitchen.
            HAEntity(
                entity_id="binary_sensor.kitchen_motion",
                name=None,
                original_name="Motion",
                icon=None,
                platform="mqtt",
                device_id=None,
                area_id="kitchen",
                disabled_by=None,
                hidden_by="user",
                unique_id="mqtt-motion-1",
                created_at="2026-01-05T00:00:00+00:00",
                modified_at="2026-01-05T00:00:00+00:00",
            ),
            # Fully-unassigned media_player, no device, no area.
            HAEntity(
                entity_id="media_player.office",
                name="Office Speaker",
                original_name=None,
                icon=None,
                platform="cast",
                device_id=None,
                area_id=None,
                disabled_by=None,
                hidden_by=None,
                unique_id="cast-office-1",
                created_at="2026-01-06T00:00:00+00:00",
                modified_at="2026-01-06T00:00:00+00:00",
            ),
        ],
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
