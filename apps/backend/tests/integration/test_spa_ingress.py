"""Serving the built frontend under Home Assistant ingress.

Ingress serves the add-on beneath `/api/hassio_ingress/<token>/` and strips
that prefix before proxying, telling us what it stripped via the
`X-Ingress-Path` header. Everything here checks that we hand the browser a
page that can find its own assets and API from under that prefix.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from home_curator.api.spa import with_base_href
from home_curator.config import Settings
from home_curator.main import create_app
from home_curator.storage.models import Base

INGRESS_PREFIX = "/api/hassio_ingress/abc123"

_INDEX_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>Home Curator</title>
    <script type="module" crossorigin src="./assets/index-abc.js"></script>
  </head>
  <body><div id="root"></div></body>
</html>
"""


# --- the injection itself ------------------------------------------------


def test_base_href_uses_the_ingress_prefix():
    out = with_base_href(_INDEX_HTML, INGRESS_PREFIX)
    assert f'<base href="{INGRESS_PREFIX}/">' in out


def test_base_href_falls_back_to_root_without_the_header():
    assert '<base href="/">' in with_base_href(_INDEX_HTML, "")


def test_base_href_is_placed_before_any_asset_reference():
    """A `<base>` after a script tag would not apply to it."""
    out = with_base_href(_INDEX_HTML, INGRESS_PREFIX)
    assert out.index("<base ") < out.index("./assets/index-abc.js")


def test_base_href_does_not_stack_on_repeated_injection():
    once = with_base_href(_INDEX_HTML, INGRESS_PREFIX)
    twice = with_base_href(once, INGRESS_PREFIX)
    assert twice.count("<base ") == 1


def test_base_href_tolerates_a_trailing_slash_on_the_header():
    out = with_base_href(_INDEX_HTML, INGRESS_PREFIX + "/")
    assert f'<base href="{INGRESS_PREFIX}/">' in out


def test_base_href_escapes_the_header_value():
    """The prefix arrives from a request header, so it is not trusted."""
    out = with_base_href(_INDEX_HTML, '/evil"><script>alert(1)</script>')
    assert "<script>alert(1)</script>" not in out
    assert "&quot;" in out


# --- serving -------------------------------------------------------------


@pytest.fixture
def static_app(tmp_path, fake_ha, monkeypatch):
    static_dir = tmp_path / "static"
    (static_dir / "assets").mkdir(parents=True)
    (static_dir / "index.html").write_text(_INDEX_HTML)
    (static_dir / "assets" / "index-abc.js").write_text("console.log('hi')")
    (static_dir / "favicon.ico").write_text("x")

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "policies.yaml").write_text("version: 1\npolicies: []")

    engine = create_engine(f"sqlite:///{tmp_path / 'curator.db'}")
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()

    monkeypatch.setenv("STATIC_DIR", str(static_dir))
    monkeypatch.setenv("CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HA_TOKEN", "devtoken")
    return create_app(ha_client=fake_ha, settings=Settings())


def test_root_carries_the_ingress_base_href(static_app):
    with TestClient(static_app) as client:
        response = client.get("/", headers={"X-Ingress-Path": INGRESS_PREFIX})
    assert response.status_code == 200
    assert f'<base href="{INGRESS_PREFIX}/">' in response.text


def test_nested_route_serves_index_not_404(static_app):
    """A hard refresh deep in the SPA must still boot the app.

    This is the case a relative `base` alone cannot handle: the browser is at
    `<prefix>/settings/devices`, so assets have to resolve against the
    injected base rather than the current path.
    """
    with TestClient(static_app) as client:
        response = client.get(
            "/settings/devices", headers={"X-Ingress-Path": INGRESS_PREFIX}
        )
    assert response.status_code == 200
    assert f'<base href="{INGRESS_PREFIX}/">' in response.text
    assert "<div id=\"root\">" in response.text


def test_assets_are_served(static_app):
    with TestClient(static_app) as client:
        response = client.get("/assets/index-abc.js")
    assert response.status_code == 200
    assert "console.log" in response.text


def test_real_files_at_the_root_are_served(static_app):
    with TestClient(static_app) as client:
        assert client.get("/favicon.ico").status_code == 200


def test_api_routes_still_win(static_app):
    with TestClient(static_app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_unknown_api_path_is_a_404_not_the_spa(static_app):
    """Otherwise an API typo would come back as HTML with a 200."""
    with TestClient(static_app) as client:
        response = client.get("/api/nope")
    assert response.status_code == 404
    assert "<div id=\"root\">" not in response.text


def test_path_traversal_falls_back_to_the_spa(static_app):
    with TestClient(static_app) as client:
        response = client.get("/../../etc/passwd")
    assert response.status_code in (200, 404)
    assert "root:" not in response.text


def test_without_the_header_the_app_still_works(static_app):
    """Direct port access and dev use send no X-Ingress-Path."""
    with TestClient(static_app) as client:
        response = client.get("/devices")
    assert response.status_code == 200
    assert '<base href="/">' in response.text
