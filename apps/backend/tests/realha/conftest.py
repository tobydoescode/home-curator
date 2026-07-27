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

import shutil
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from testcontainers.core.container import DockerContainer

from home_curator.ha_client.websocket import WebSocketHAClient

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


# Every module in this package must declare `pytestmark = pytest.mark.realha`.
# Marking them from a `pytest_collection_modifyitems` hook here does not work:
# the hook is handed *every* collected item rather than only this package's,
# and it runs after pytest has already applied `-m` deselection.


@pytest.fixture(scope="session")
def ha_base_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """Boot a throwaway Home Assistant and yield its base URL."""
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


@pytest_asyncio.fixture
async def ha_client(ha_ws_url: str, ha_token: str):
    """A started, authenticated `WebSocketHAClient` — the real thing."""
    client = WebSocketHAClient(url=ha_ws_url, token=ha_token)
    await client.start()
    try:
        yield client
    finally:
        await client.stop()
