import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from home_curator.config import Settings
from home_curator.main import create_app
from home_curator.storage.models import Base


@pytest.fixture
def client(tmp_path, fake_ha, monkeypatch):
    """Client fixture with a custom policy seeded alongside the standard ones."""
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
  - id: no-area-custom
    type: custom
    enabled: true
    severity: info
    scope: devices
    when: "true"
    assert: "device.area_id != null"
    message: "Device has no room"
""".strip()
    )
    engine = create_engine(f"sqlite:///{tmp_path / 'curator.db'}")
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()
    monkeypatch.setenv("CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HA_TOKEN", "devtoken")
    app = create_app(ha_client=fake_ha, settings=Settings())
    with TestClient(app) as c:
        yield c


def test_simulate_draft_custom_devices(client):
    body = {
        "policy": {
            "id": "t", "type": "custom", "scope": "devices", "severity": "info",
            "when": "true", "assert": "device.area_id != null", "message": "No room",
        },
    }
    r = client.post("/api/policies/simulate", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    # Fixture should have at least one device with no area; see conftest.
    assert data["counts"]["fails_assert"] >= 1
    assert any("No room" in row["message"] for row in data["failing"])


def test_simulate_draft_naming_skipped_gracefully(client):
    body = {
        "policy": {
            "id": "nc", "type": "naming_convention", "severity": "warning",
            "global": {"preset": "snake_case"}, "starts_with_room": False, "rooms": [],
        },
    }
    r = client.post("/api/policies/simulate", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True


def test_simulate_invalid_cel(client):
    body = {
        "policy": {
            "id": "t", "type": "custom", "scope": "devices", "severity": "info",
            "when": "true", "assert": "device.area_id &&&", "message": "x",
        },
    }
    r = client.post("/api/policies/simulate", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is False
    assert data["error"]


def test_simulate_by_policy_id(client):
    listing = client.get("/api/policies").json()
    custom_ids = [p["id"] for p in listing["policies"] if p["type"] == "custom"]
    assert custom_ids, "fixture should include at least one custom policy"
    r = client.post("/api/policies/simulate", json={"policy_id": custom_ids[0]})
    assert r.status_code == 200
    assert r.json()["ok"] is True
