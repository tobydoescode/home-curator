"""The whole app against a real Home Assistant.

Everything else in this package exercises `WebSocketHAClient` in isolation.
This boots the actual FastAPI app — lifespan, registry caches, deletion
tracker, rule engine — against real HA data, which is the closest thing to
what the add-on does in production.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient

from alembic import command
from home_curator.config import Settings
from home_curator.ha_client.websocket import WebSocketHAClient
from home_curator.main import create_app

pytestmark = pytest.mark.realha

_POLICIES = """
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


def _migrate(db_path: Path) -> None:
    """Build the schema the way production does, not via create_all."""
    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    cfg.set_main_option("script_location", str(root / "alembic"))
    command.upgrade(cfg, "head")


@pytest.fixture
def real_app(tmp_path, ha_ws_url, ha_token, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "policies.yaml").write_text(_POLICIES)
    _migrate(tmp_path / "curator.db")

    monkeypatch.setenv("CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HA_TOKEN", ha_token)

    # Unstarted on purpose — the app's lifespan owns start/stop.
    client = WebSocketHAClient(url=ha_ws_url, token=ha_token)
    return create_app(ha_client=client, settings=Settings())


def test_devices_endpoint_serves_real_registry_data(real_app):
    with TestClient(real_app) as client:
        response = client.get("/api/devices")
    assert response.status_code == 200

    body = response.json()
    by_name = {d["name"]: d for d in body["devices"]}
    assert "living_room_lamp" in by_name
    assert "BadCase" in by_name

    lamp = by_name["living_room_lamp"]
    assert lamp["area_name"] == "Living Room"
    assert lamp["integration"] == "curator_test"
    assert {"Living Room", "Kitchen", "Garage"} <= {
        a["name"] for a in body["all_areas"]
    }


def test_policies_evaluate_against_real_devices(real_app):
    """`BadCase` violates both seeded rules; the lamp violates neither."""
    with TestClient(real_app) as client:
        body = client.get("/api/devices").json()

    by_name = {d["name"]: d for d in body["devices"]}

    bad = by_name["BadCase"]
    rule_types = {issue["rule_type"] for issue in bad["issues"]}
    assert "missing_area" in rule_types, "no area assigned, so missing_area must fire"
    assert "naming_convention" in rule_types, "'BadCase' is not snake_case"

    lamp = by_name["living_room_lamp"]
    assert lamp["issue_count"] == 0, lamp["issues"]


def test_entities_endpoint_serves_real_registry_data(real_app):
    with TestClient(real_app) as client:
        response = client.get("/api/entities")
    assert response.status_code == 200

    body = response.json()
    by_id = {e["entity_id"]: e for e in body["entities"]}

    # Disabled and hidden entities are excluded unless explicitly requested.
    assert "switch.garage_door" not in by_id
    assert "binary_sensor.kitchen_motion" not in by_id

    lamp = by_id["light.lamp"]
    assert lamp["platform"] == "hue"
    assert lamp["display_name"] == "Living Room Lamp"
    # The entity has no area of its own — this proves the device fallback.
    assert lamp["area_id"] is None
    assert lamp["area_name"] == "Living Room"
    assert lamp["device_name"] == "living_room_lamp"


def test_entities_endpoint_can_include_disabled_and_hidden(real_app):
    with TestClient(real_app) as client:
        body = client.get(
            "/api/entities", params={"show_disabled": True, "show_hidden": True}
        ).json()

    by_id = {e["entity_id"]: e for e in body["entities"]}
    assert by_id["switch.garage_door"]["disabled_by"] == "user"
    assert by_id["binary_sensor.kitchen_motion"]["hidden_by"] == "user"


def test_areas_endpoint_serves_real_areas(real_app):
    with TestClient(real_app) as client:
        areas = client.get("/api/areas").json()
    assert {"Living Room", "Kitchen", "Garage"} <= {a["name"] for a in areas}


def test_resync_against_real_ha(real_app):
    """The manual resync path re-pulls both registries without erroring."""
    with TestClient(real_app) as client:
        response = client.post("/api/cache/resync")
    assert response.status_code == 200
    body = response.json()
    for key in ("added", "removed", "updated"):
        assert key in body
        assert isinstance(body[key], int)
