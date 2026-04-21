from pathlib import Path

from home_curator.config import Settings


def test_defaults_in_dev(tmp_path, monkeypatch):
    monkeypatch.delenv("SUPERVISOR_TOKEN", raising=False)
    monkeypatch.chdir(tmp_path)
    s = Settings()
    assert s.config_dir == tmp_path / ".dev-config" / "home-curator"
    assert s.data_dir == tmp_path / ".dev-data"
    assert s.ha_url == "http://localhost:8123"
    assert s.ha_token is None
    assert s.effective_token is None


def test_defaults_with_supervisor_token(monkeypatch):
    monkeypatch.setenv("SUPERVISOR_TOKEN", "fake")
    s = Settings()
    assert s.config_dir == Path("/config/home-curator")
    assert s.data_dir == Path("/data")
    assert s.ha_url == "http://supervisor/core"
    assert s.ha_token == "fake"


def test_override_via_env(monkeypatch):
    monkeypatch.setenv("CONFIG_DIR", "/tmp/cfg")
    monkeypatch.setenv("DATA_DIR", "/tmp/data")
    monkeypatch.setenv("HA_URL", "http://example")
    monkeypatch.setenv("HA_TOKEN", "tok")
    s = Settings()
    assert s.config_dir == Path("/tmp/cfg")
    assert s.data_dir == Path("/tmp/data")
    assert s.ha_url == "http://example"
    assert s.ha_token == "tok"
    assert s.effective_token == "tok"
    assert s.db_path == Path("/tmp/data/curator.db")
    assert s.policies_path == Path("/tmp/cfg/policies.yaml")


def test_ha_token_overrides_supervisor_when_both_set(monkeypatch):
    monkeypatch.setenv("SUPERVISOR_TOKEN", "supervisor")
    monkeypatch.setenv("HA_TOKEN", "explicit")
    s = Settings()
    assert s.supervisor_token == "supervisor"
    assert s.ha_token == "explicit"
    assert s.effective_token == "explicit"
