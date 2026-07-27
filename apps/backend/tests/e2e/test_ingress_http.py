"""Ingress checks that need no browser.

Follows the same chain a browser would: fetch the page, read the `<base
href>` it was given, then resolve the page's own asset and API URLs against
that base and confirm they are reachable. If any link in that chain is
absolute, one of these fails.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

import httpx
import pytest

pytestmark = pytest.mark.e2e

_BASE_HREF = re.compile(r'<base\s+href="([^"]+)"', re.IGNORECASE)
_ASSET_SRC = re.compile(r'<script[^>]+src="([^"]+)"', re.IGNORECASE)
_STYLESHEET = re.compile(r'<link[^>]+rel="stylesheet"[^>]+href="([^"]+)"', re.IGNORECASE)


def _page(url: str) -> tuple[str, str]:
    """Fetch `url`, returning its HTML and the absolute base it declares."""
    response = httpx.get(url, timeout=30, follow_redirects=True)
    assert response.status_code == 200, response.text[:400]
    match = _BASE_HREF.search(response.text)
    assert match, "page was served without a <base href>"
    return response.text, urljoin(str(response.url), match.group(1))


def test_page_declares_the_ingress_prefix_as_its_base(ingress_base_url):
    _, base = _page(f"{ingress_base_url}/")
    assert base.endswith("/api/hassio_ingress/testtoken/"), base


def test_scripts_and_styles_resolve_under_the_prefix(ingress_base_url):
    """The failure this catches: Vite emitting `/assets/…` absolute."""
    html, base = _page(f"{ingress_base_url}/")

    refs = _ASSET_SRC.findall(html) + _STYLESHEET.findall(html)
    assert refs, "index.html referenced no assets — was the frontend built?"

    for ref in refs:
        resolved = urljoin(base, ref)
        assert "/api/hassio_ingress/testtoken/" in resolved, (
            f"{ref!r} resolved to {resolved!r}, outside the ingress prefix"
        )
        assert httpx.get(resolved, timeout=30).status_code == 200, resolved


def test_api_resolves_under_the_prefix(ingress_base_url):
    _, base = _page(f"{ingress_base_url}/")

    health = httpx.get(urljoin(base, "api/health"), timeout=30)
    assert health.status_code == 200
    assert health.json() == {"ok": True}

    devices = httpx.get(urljoin(base, "api/devices"), timeout=30)
    assert devices.status_code == 200
    assert any(d["name"] == "living_room_lamp" for d in devices.json()["devices"])


def test_nested_route_gets_the_same_absolute_base(ingress_base_url):
    """The case relative-only paths cannot survive.

    At `<prefix>/settings/devices`, a relative `./assets/x.js` would resolve
    to `<prefix>/settings/assets/x.js`. The injected base is absolute, so the
    depth of the route must not matter.
    """
    _, root_base = _page(f"{ingress_base_url}/")
    html, nested_base = _page(f"{ingress_base_url}/settings/devices")

    assert nested_base == root_base

    for ref in _ASSET_SRC.findall(html) + _STYLESHEET.findall(html):
        assert httpx.get(urljoin(nested_base, ref), timeout=30).status_code == 200


def test_sse_stream_is_reachable_under_the_prefix(ingress_base_url):
    _, base = _page(f"{ingress_base_url}/")
    with httpx.stream(
        "GET", urljoin(base, "api/events"), timeout=30
    ) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
