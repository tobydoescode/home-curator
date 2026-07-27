"""Ingress checks that need a real browser.

The HTTP-level tests prove the page's URLs resolve under the prefix. They
cannot prove the app actually boots there — that requires the bundle to
execute and the router to match. A wrong `BrowserRouter` basename passes
every HTTP check and still renders nothing but "Not Found".
"""

from __future__ import annotations

import pytest

# `-m 'not e2e'` deselects this module but pytest still imports it during
# collection, so a bare top-level import would break the default suite for
# anyone without the optional `e2e` group installed.
pytest.importorskip(
    "playwright.sync_api",
    reason="install the optional 'e2e' dependency group to run these",
)

from playwright.sync_api import Page, expect  # noqa: E402

pytestmark = pytest.mark.e2e


@pytest.fixture
def failures(page: Page) -> list[str]:
    """Collect console errors and failed requests for assertion."""
    collected: list[str] = []
    page.on(
        "console",
        lambda msg: collected.append(f"console: {msg.text}")
        if msg.type == "error"
        else None,
    )
    page.on(
        "requestfailed",
        lambda req: collected.append(f"requestfailed: {req.url}"),
    )
    page.on(
        "response",
        lambda res: collected.append(f"HTTP {res.status}: {res.url}")
        if res.status >= 400
        else None,
    )
    return collected


def test_app_boots_under_the_ingress_prefix(page: Page, failures, ingress_base_url):
    page.goto(f"{ingress_base_url}/", wait_until="load")

    # Root redirects to /devices; the heading only renders if the bundle
    # loaded, the router matched, and GET api/devices resolved correctly.
    expect(page.get_by_role("heading", name="Devices")).to_be_visible()
    assert not failures, failures


def test_data_from_the_api_renders(page: Page, ingress_base_url):
    page.goto(f"{ingress_base_url}/", wait_until="load")
    expect(page.get_by_text("living_room_lamp")).to_be_visible()


def test_router_basename_matches_the_prefix(page: Page, ingress_base_url):
    """Root must land on /devices *inside* the prefix, not above it."""
    page.goto(f"{ingress_base_url}/", wait_until="load")
    # The redirect is client-side, so wait for it to have rendered.
    expect(page.get_by_role("heading", name="Devices")).to_be_visible()
    assert page.url.startswith(f"{ingress_base_url}/devices"), page.url


def test_hard_refresh_on_a_nested_route_works(
    page: Page, failures, ingress_base_url
):
    """The case that motivated `<base href>` over a relative base.

    Loading `<prefix>/settings/devices` directly means assets must resolve
    against the injected base rather than the current path.
    """
    page.goto(f"{ingress_base_url}/settings/devices", wait_until="load")

    expect(page.get_by_role("heading", name="Device Settings")).to_be_visible()
    assert not failures, failures


def test_client_side_navigation_stays_under_the_prefix(page: Page, ingress_base_url):
    page.goto(f"{ingress_base_url}/", wait_until="load")

    page.get_by_role("link", name="Entities").click()

    expect(page.get_by_role("heading", name="Entities")).to_be_visible()
    assert page.url.startswith(f"{ingress_base_url}/entities"), page.url
