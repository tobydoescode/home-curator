"""`create_app(settings=...)` must be what the handlers actually use.

Two handlers built their own `Settings()` instead of reading the instance the
app was created with, so the argument was silently ignored and the process
environment won instead. The integration fixtures happened to set both, which
is why nothing caught it.

`Settings` also loads `.env`, so constructing one per request meant a
filesystem read inside the request path for configuration that cannot change
while the app is running.
"""

import pytest
from fastapi.testclient import TestClient
from ruamel.yaml import YAML
from sqlalchemy import create_engine

from home_curator.config import Settings
from home_curator.main import create_app
from home_curator.storage.models import Base


@pytest.fixture
def app_with_diverging_env(tmp_path, fake_ha, monkeypatch):
    """Injected settings point at one directory; the environment at another."""
    injected = tmp_path / "injected"
    injected.mkdir()
    decoy = tmp_path / "from-environment"
    decoy.mkdir()

    engine = create_engine(f"sqlite:///{tmp_path / 'curator.db'}")
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()

    # The environment deliberately disagrees with what is injected below.
    monkeypatch.setenv("CONFIG_DIR", str(decoy))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HA_TOKEN", "devtoken")
    monkeypatch.setenv("HA_EXTERNAL_URL", "http://from-environment.invalid")

    settings = Settings(
        CONFIG_DIR=injected,
        DATA_DIR=tmp_path,
        HA_TOKEN="devtoken",
        HA_EXTERNAL_URL="http://injected.invalid",
    )
    return create_app(ha_client=fake_ha, settings=settings), injected, decoy


def test_policies_are_written_where_the_injected_settings_say(
    app_with_diverging_env,
):
    app, injected, decoy = app_with_diverging_env

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

    written = injected / "policies.yaml"
    assert written.is_file(), "policies were not written where the app was told"
    assert not (decoy / "policies.yaml").exists(), (
        "handler used the environment instead of the injected settings"
    )

    parsed = YAML(typ="safe").load(written.read_text())
    assert [p["id"] for p in parsed["policies"]] == ["missing-room"]


def test_config_endpoint_reads_the_injected_settings(app_with_diverging_env):
    app, _, _ = app_with_diverging_env

    with TestClient(app) as client:
        body = client.get("/api/config").json()

    assert body["ha_external_url"] == "http://injected.invalid"


def test_startup_seeds_into_the_injected_directory(app_with_diverging_env):
    """Seeding already used the injected settings; this pins that down."""
    app, injected, decoy = app_with_diverging_env

    with TestClient(app):
        pass

    assert (injected / "policies.yaml").is_file()
    assert not (decoy / "policies.yaml").exists()
