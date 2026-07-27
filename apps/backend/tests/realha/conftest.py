"""Harness for tests that run against a real Home Assistant instance.

Home Curator talks to Home Assistant over websocket commands that live in
HA's `config` integration — `config/device_registry/list`,
`config/entity_registry/update`, `config/device_registry/remove_config_entry`
and friends. Those commands are first-party and are the supported route for
programmatic registry work (the REST API exposes no registry at all), but
they are absent from HA's published API reference. There is therefore no
written spec to code `ha_client/websocket.py` against.

These tests supply the missing spec: a pinned Home Assistant container with a
known registry shape, driven through the real `WebSocketHAClient`.

Everything here is marked `realha` and deselected by default. Run with
`task test:realha`.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import time
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pytest
import pytest_asyncio
from websockets.asyncio.client import connect

from home_curator.ha_client.websocket import WebSocketHAClient

if TYPE_CHECKING:
    from testcontainers.core.container import DockerContainer

# Pinned so fixture expectations cannot drift underneath us. Renovate will
# raise a PR to bump this; a failure on that PR is an early warning that HA
# changed a command Home Curator depends on.
HA_IMAGE = "ghcr.io/home-assistant/home-assistant:2026.7.4"

_FIXTURE_CONFIG = Path(__file__).parent / "fixtures" / "config"

# Home Assistant's first boot unpacks and sets up every listed integration.
# Cold start in CI is comfortably under two minutes; the ceiling is generous
# because an image pull may be counted against it on a cold runner.
_BOOT_TIMEOUT_SECONDS = 300
_ONBOARD_USERNAME = "curator"
_ONBOARD_PASSWORD = "curator-test-password"

# Config entries are set up asynchronously after HA starts answering HTTP,
# so tests wait for a known fixture device rather than for the port.
_FIXTURE_TIMEOUT_SECONDS = 120
_FIXTURE_SENTINEL_DEVICE = "living_room_lamp"


# Every module in this package must declare `pytestmark = pytest.mark.realha`.
# Marking them from a `pytest_collection_modifyitems` hook here does not work:
# the hook is handed *every* collected item rather than only this package's,
# and it runs after pytest has already applied `-m` deselection.


@pytest.fixture(scope="session")
def ha_base_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """Boot a throwaway Home Assistant and yield its base URL."""
    # Imported here rather than at module scope on purpose. `-m 'not realha'`
    # deselects these tests but pytest still *imports* this conftest during
    # collection, so a module-level import would make the default suite fail
    # for anyone who has not installed the optional `realha` group.
    from testcontainers.core.container import DockerContainer

    config_dir = tmp_path_factory.mktemp("ha-config")
    shutil.copytree(_FIXTURE_CONFIG, config_dir, dirs_exist_ok=True)

    container = (
        DockerContainer(HA_IMAGE)
        .with_exposed_ports(8123)
        .with_volume_mapping(str(config_dir), "/config", "rw")
        .with_env("TZ", "Etc/UTC")
    )

    with container:
        base_url = (
            f"http://{container.get_container_host_ip()}:"
            f"{container.get_exposed_port(8123)}"
        )
        _wait_until_responsive(container, base_url)
        yield base_url


def _wait_until_responsive(container: DockerContainer, base_url: str) -> None:
    """Poll until HA answers, then fail loudly with its logs if it never does."""
    deadline = time.monotonic() + _BOOT_TIMEOUT_SECONDS
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = httpx.get(base_url, timeout=5)
        except httpx.HTTPError as exc:
            last_error = exc
        else:
            if response.status_code < 500:
                return
            last_error = RuntimeError(f"HTTP {response.status_code}")
        time.sleep(2)

    stdout, stderr = container.get_logs()
    raise TimeoutError(
        f"Home Assistant did not become responsive within "
        f"{_BOOT_TIMEOUT_SECONDS}s (last error: {last_error}).\n"
        f"--- container stdout ---\n{stdout.decode(errors='replace')}\n"
        f"--- container stderr ---\n{stderr.decode(errors='replace')}"
    )


@pytest.fixture(scope="session")
def ha_token(ha_base_url: str) -> str:
    """Complete onboarding and exchange the auth code for an access token.

    A fresh config directory means onboarding has not run, so
    `/api/onboarding/users` is reachable unauthenticated. It returns an
    auth code, which `/auth/token` exchanges for a bearer token. A
    long-lived token is unnecessary — the access token outlives the suite.
    """
    client_id = f"{ha_base_url}/"

    created = httpx.post(
        f"{ha_base_url}/api/onboarding/users",
        json={
            "client_id": client_id,
            "name": "Curator Test",
            "username": _ONBOARD_USERNAME,
            "password": _ONBOARD_PASSWORD,
            "language": "en",
        },
        timeout=60,
    )
    if created.status_code == 403:
        pytest.fail(
            "Home Assistant reported onboarding as already complete. The "
            "config directory should be freshly created per session."
        )
    created.raise_for_status()

    exchanged = httpx.post(
        f"{ha_base_url}/auth/token",
        data={
            "grant_type": "authorization_code",
            "code": created.json()["auth_code"],
            "client_id": client_id,
        },
        timeout=60,
    )
    exchanged.raise_for_status()
    return exchanged.json()["access_token"]


@pytest.fixture(scope="session")
def ha_ws_url(ha_base_url: str) -> str:
    return ha_base_url.replace("http://", "ws://") + "/api/websocket"


@pytest.fixture(scope="session")
def ha_ready(ha_ws_url: str, ha_token: str) -> None:
    """Block until the fixture integration has populated the registries.

    Home Assistant serves HTTP well before it has finished setting up every
    integration, so "the port answers" is not the same as "the devices
    exist". Without this gate the first test to run sees an empty device
    registry, intermittently, depending on how fast the container warms up.
    """
    deadline = time.monotonic() + _FIXTURE_TIMEOUT_SECONDS
    seen: list[str] = []
    while time.monotonic() < deadline:
        seen = asyncio.run(_list_device_names(ha_ws_url, ha_token))
        if _FIXTURE_SENTINEL_DEVICE in seen:
            return
        time.sleep(1)

    raise TimeoutError(
        f"fixture device {_FIXTURE_SENTINEL_DEVICE!r} never appeared in the "
        f"device registry within {_FIXTURE_TIMEOUT_SECONDS}s. Saw: {seen}. "
        "Check that the curator_test custom component loaded — its errors "
        "surface in the container log."
    )


async def _list_device_names(ws_url: str, token: str) -> list[str]:
    """One-shot device registry read, independent of `WebSocketHAClient`.

    Readiness must not depend on the class under test.
    """
    try:
        async with connect(ws_url, max_size=None) as ws:
            if json.loads(await ws.recv()).get("type") != "auth_required":
                return []
            await ws.send(json.dumps({"type": "auth", "access_token": token}))
            if json.loads(await ws.recv()).get("type") != "auth_ok":
                return []
            await ws.send(json.dumps({"id": 1, "type": "config/device_registry/list"}))
            while True:
                message = json.loads(await ws.recv())
                if message.get("id") == 1 and message.get("type") == "result":
                    if not message.get("success"):
                        return []
                    return [d.get("name") for d in message.get("result") or []]
    except (OSError, ConnectionError, json.JSONDecodeError):
        return []


@pytest_asyncio.fixture
async def ha_client(ha_ws_url: str, ha_token: str, ha_ready: None):
    """A started, authenticated `WebSocketHAClient` — the real thing."""
    client = WebSocketHAClient(url=ha_ws_url, token=ha_token)
    await client.start()
    try:
        yield client
    finally:
        await client.stop()
