import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from home_curator.config import Settings
from home_curator.main import create_app
from home_curator.storage.models import Base


@pytest.fixture
def client(tmp_path, fake_ha, monkeypatch):
    """Client with a policies.yaml that includes an entity-scope custom rule."""
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
  - id: entity-aqara-named
    type: custom
    scope: entities
    enabled: true
    severity: info
    when: 'entity.platform == "aqara"'
    assert: 'entity.name != null'
    message: "Aqara entity missing a friendly name"
""".strip()
    )
    engine = create_engine(f"sqlite:///{tmp_path / 'curator.db'}")
    Base.metadata.create_all(engine)
    monkeypatch.setenv("CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HA_TOKEN", "devtoken")
    app = create_app(ha_client=fake_ha, settings=Settings())
    with TestClient(app) as c:
        yield c


def test_simulate_entity_scope_custom_iterates_entities(client):
    body = {
        "policy": {
            "id": "t", "type": "custom", "scope": "entities", "severity": "info",
            "when": 'entity.platform == "aqara"',
            "assert": "entity.name != null",
            "message": "Aqara entity missing a friendly name",
        },
    }
    r = client.post("/api/policies/simulate", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    # Fixture has one Aqara entity (sensor.temperature) with name=None,
    # so one matches when and fails assert.
    assert data["counts"]["matched_when"] == 1
    assert data["counts"]["fails_assert"] == 1
    [row] = data["failing"]
    assert row["id"] == "sensor.temperature"
    assert row["name"] == "Temperature"  # from original_name fallback


def test_simulate_entity_scope_by_policy_id(client):
    # The fixture's entity-aqara-named custom policy is entity-scope.
    r = client.post(
        "/api/policies/simulate",
        json={"policy_id": "entity-aqara-named"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["counts"]["fails_assert"] == 1


def test_simulate_non_custom_at_entity_scope_zero_counts(client):
    # Non-custom at entity scope (e.g. entity_naming_convention) returns
    # ok=true with zero counts — simulation is only meaningful for CEL.
    body = {
        "policy": {
            "id": "x",
            "type": "entity_naming_convention",
            "severity": "warning",
            "name": {
                "global": {"preset": "title-case"},
                "starts_with_room": False,
                "rooms": [],
            },
            "entity_id": {"starts_with_room": False, "rooms": []},
        },
    }
    r = client.post("/api/policies/simulate", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["counts"]["matched_when"] == 0


def test_compile_entity_naming_convention_schema_only(client):
    r = client.post(
        "/api/policies/compile",
        json={
            "id": "x",
            "type": "entity_naming_convention",
            "severity": "warning",
            "name": {
                "global": {"preset": "title-case"},
                "starts_with_room": False,
                "rooms": [],
            },
            "entity_id": {"starts_with_room": False, "rooms": []},
        },
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True, "error": None, "position": None}


def test_compile_entity_missing_area_schema_only(client):
    r = client.post(
        "/api/policies/compile",
        json={
            "id": "x",
            "type": "entity_missing_area",
            "severity": "info",
            "require_own_area": False,
        },
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True, "error": None, "position": None}
