"""First run of the addon, when /config/home-curator does not exist yet.

`Settings` points `config_dir` at `/config/home-curator` under the addon.
That directory does not exist on a fresh install, and nothing used to create
it — so the first policy save raised FileNotFoundError out of the writer and
came back as an unhandled 500.

Nothing caught this because every other path pre-creates the directory:
`task setup` runs `mkdir -p .dev-config/home-curator`, and the integration
fixtures build `config_dir` themselves. These tests deliberately do not.
"""

import pytest
from fastapi.testclient import TestClient
from ruamel.yaml import YAML
from sqlalchemy import create_engine

from home_curator.config import Settings
from home_curator.main import create_app
from home_curator.storage.models import Base


@pytest.fixture
def app_without_config_dir(tmp_path, fake_ha, monkeypatch):
    """An app whose `config_dir` does not exist — a fresh addon install."""
    engine = create_engine(f"sqlite:///{tmp_path / 'curator.db'}")
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()

    config_dir = tmp_path / "config" / "home-curator"
    assert not config_dir.exists()

    monkeypatch.setenv("CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HA_TOKEN", "devtoken")
    return create_app(ha_client=fake_ha, settings=Settings()), config_dir


def test_startup_seeds_the_policies_file(app_without_config_dir):
    """The addon README tells users they can edit this file directly, so it
    has to exist before they have saved anything through the UI."""
    app, config_dir = app_without_config_dir

    with TestClient(app):
        pass

    policies = config_dir / "policies.yaml"
    assert policies.is_file()

    data = YAML(typ="safe").load(policies.read_text())
    assert data["version"] == 1
    ids = {p["id"] for p in data["policies"]}
    assert {"naming-convention", "missing-room", "reappeared"} <= ids


def test_seeded_policies_are_served_by_the_api(app_without_config_dir):
    app, _ = app_without_config_dir

    with TestClient(app) as client:
        body = client.get("/api/policies").json()

    assert body["error"] is None
    assert {p["id"] for p in body["policies"]}


def test_first_policy_save_succeeds(app_without_config_dir):
    """The original bug: this returned an unhandled 500."""
    app, config_dir = app_without_config_dir

    with TestClient(app) as client:
        response = client.put(
            "/api/policies",
            json={
                "version": 1,
                "policies": [
                    {
                        "id": "missing-room",
                        "type": "missing_area",
                        "enabled": True,
                        "severity": "warning",
                    }
                ],
            },
        )

    assert response.status_code == 200, response.text
    assert response.json() == {"ok": True, "error": None}

    saved = YAML(typ="safe").load((config_dir / "policies.yaml").read_text())
    assert [p["id"] for p in saved["policies"]] == ["missing-room"]


def test_seeding_does_not_overwrite_an_existing_file(tmp_path, fake_ha, monkeypatch):
    """A user's customisations must survive every restart."""
    engine = create_engine(f"sqlite:///{tmp_path / 'curator.db'}")
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()

    config_dir = tmp_path / "config" / "home-curator"
    config_dir.mkdir(parents=True)
    (config_dir / "policies.yaml").write_text(
        "# hand-written\n"
        "version: 1\n"
        "policies:\n"
        "  - id: only-mine\n"
        "    type: missing_area\n"
        "    enabled: false\n"
        "    severity: info\n"
    )

    monkeypatch.setenv("CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HA_TOKEN", "devtoken")
    app = create_app(ha_client=fake_ha, settings=Settings())

    with TestClient(app):
        pass

    text = (config_dir / "policies.yaml").read_text()
    assert "# hand-written" in text
    assert "only-mine" in text


def test_unwritable_config_dir_reports_cleanly(tmp_path, fake_ha, monkeypatch):
    """A read-only /config should still boot, and a save should explain itself."""
    engine = create_engine(f"sqlite:///{tmp_path / 'curator.db'}")
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()

    readonly = tmp_path / "readonly"
    readonly.mkdir()
    config_dir = readonly / "home-curator"

    monkeypatch.setenv("CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HA_TOKEN", "devtoken")
    app = create_app(ha_client=fake_ha, settings=Settings())

    readonly.chmod(0o500)
    try:
        # Boots despite being unable to seed — a read-only config mount
        # should still give a working, read-only app.
        with TestClient(app) as client:
            assert client.get("/api/health").status_code == 200

            response = client.put(
                "/api/policies", json={"version": 1, "policies": []}
            )
        assert response.status_code == 500
        assert "could not write" in response.json()["detail"]
    finally:
        readonly.chmod(0o700)
