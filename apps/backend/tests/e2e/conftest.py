"""A fake Home Assistant ingress in front of the real app.

Ingress's contract is narrow enough to reproduce faithfully: serve the
add-on beneath a path prefix, strip that prefix before proxying, and pass
what was stripped in an `X-Ingress-Path` header. That is what this harness
does, in front of the real backend serving the real built frontend.

It exists because the ingress bug class is invisible to every other test we
have — the app is only ever exercised at the origin root, where absolute
paths happen to work.

This does not prove my model of ingress is correct; it guards the regression
once the model has been validated against a real Supervisor. Everything here
is marked `e2e` and deselected by default.
"""

from __future__ import annotations

import os
import socket
import threading
import time
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
import uvicorn
from sqlalchemy import create_engine
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.types import ASGIApp, Receive, Scope, Send

from home_curator.config import Settings
from home_curator.ha_client.fake import FakeHAClient
from home_curator.ha_client.models import HAArea, HADevice, HADeviceEntityRef, HAEntity
from home_curator.main import create_app
from home_curator.storage.models import Base

# Arbitrary, but shaped like the real thing: HA uses a per-session token.
INGRESS_PREFIX = "/api/hassio_ingress/testtoken"

_FRONTEND_DIST = Path(__file__).resolve().parents[3] / "frontend" / "dist"

_POLICIES = """
version: 1
policies:
  - id: missing-room
    type: missing_area
    enabled: true
    severity: warning
""".strip()


class _AddIngressHeader:
    """Set `X-Ingress-Path`, exactly as the Supervisor's proxy does."""

    def __init__(self, app: ASGIApp, prefix: str) -> None:
        self._app = app
        self._prefix = prefix.encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            scope = dict(scope)
            scope["headers"] = [
                *scope["headers"],
                (b"x-ingress-path", self._prefix),
            ]
        await self._app(scope, receive, send)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def built_frontend() -> Path:
    if not (_FRONTEND_DIST / "index.html").is_file():
        pytest.skip(
            "apps/frontend/dist is missing — run `npm run gen:api:local && "
            "npm run build` in apps/frontend first"
        )
    return _FRONTEND_DIST


@pytest.fixture(scope="session")
def ingress_base_url(built_frontend: Path, tmp_path_factory) -> Iterator[str]:
    """Serve the real app behind the fake ingress and yield its public URL."""
    workdir = tmp_path_factory.mktemp("ingress")
    config_dir = workdir / "config"
    config_dir.mkdir()
    (config_dir / "policies.yaml").write_text(_POLICIES)

    engine = create_engine(f"sqlite:///{workdir / 'curator.db'}")
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()

    settings = Settings(
        CONFIG_DIR=str(config_dir),  # type: ignore[call-arg]
        DATA_DIR=str(workdir),  # type: ignore[call-arg]
        HA_TOKEN="devtoken",  # type: ignore[call-arg]
    )

    os.environ["STATIC_DIR"] = str(built_frontend)
    app = create_app(ha_client=_fake_ha(), settings=settings)

    # Starlette's Mount rewrites `path` and moves the prefix to `root_path`,
    # which is precisely how ingress presents requests to the add-on.
    @asynccontextmanager
    async def lifespan(_):
        async with app.router.lifespan_context(app):
            yield

    outer = Starlette(
        routes=[Mount(INGRESS_PREFIX, app=_AddIngressHeader(app, INGRESS_PREFIX))],
        lifespan=lifespan,
    )

    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(outer, host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 30
    while not server.started:
        if time.monotonic() > deadline:
            raise TimeoutError("fake-ingress server did not start")
        time.sleep(0.05)

    try:
        yield f"http://127.0.0.1:{port}{INGRESS_PREFIX}"
    finally:
        server.should_exit = True
        thread.join(timeout=30)


def _fake_ha() -> FakeHAClient:
    return FakeHAClient(
        devices=[
            HADevice(
                id="d1",
                name="living_room_lamp",
                name_by_user=None,
                manufacturer="Signify",
                model="m",
                area_id="living",
                integration="hue",
                disabled_by=None,
                identifiers=[["hue", "a"]],
                config_entries=["e1"],
                entities=[HADeviceEntityRef(id="light.lamp", domain="light")],
            ),
        ],
        areas=[HAArea(id="living", name="Living Room")],
        entities=[
            HAEntity(
                entity_id="light.lamp",
                name=None,
                original_name="Living Room Lamp",
                icon=None,
                platform="hue",
                device_id="d1",
                area_id=None,
                disabled_by=None,
                hidden_by=None,
                unique_id="hue-lamp-1",
            ),
        ],
    )
