"""SSE entity event integration tests.

Mirrors the pattern in test_events_sse.py: spin uvicorn on an ephemeral
port in a background thread so SSE actually streams (TestClient and
httpx.ASGITransport both buffer the full response body, so in-process
mocks can't exercise SSE realistically).

Cross-loop coordination: uvicorn runs in its own event loop (thread); we
publish into the broker via run_coroutine_threadsafe so queue ops stay
inside the loop that owns them.
"""
import asyncio
import json
import socket
import threading

import httpx
import pytest
import uvicorn

pytestmark = [
    pytest.mark.filterwarnings(
        "ignore:websockets\\.legacy is deprecated:DeprecationWarning"
    ),
    pytest.mark.filterwarnings(
        "ignore:websockets\\.server\\.WebSocketServerProtocol is deprecated:DeprecationWarning"
    ),
]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Server(uvicorn.Server):
    """uvicorn.Server that exposes its running event loop and a ready event."""

    def __init__(self, config: uvicorn.Config) -> None:
        super().__init__(config)
        self.ready = threading.Event()
        self.server_loop: asyncio.AbstractEventLoop | None = None

    def install_signal_handlers(self) -> None:
        pass  # don't touch process-level signals in tests

    async def startup(self, sockets=None) -> None:
        self.server_loop = asyncio.get_running_loop()
        await super().startup(sockets=sockets)
        self.ready.set()


async def _run_sse_emit_and_collect(
    app_with_fake, publish_event: dict, expected_kind: str,
) -> dict | None:
    """Shared helper: start the server, publish `publish_event` via the
    broker (simulating what main.py's on_event handler does in prod), and
    collect the first matching SSE `data:` payload."""
    port = _free_port()
    config = uvicorn.Config(
        app=app_with_fake,
        host="127.0.0.1",
        port=port,
        log_level="error",
        loop="asyncio",
    )
    server = _Server(config)
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    assert server.ready.wait(timeout=5.0), "uvicorn did not start in time"
    assert server.server_loop is not None

    found: dict | None = None
    try:
        async with httpx.AsyncClient(
            base_url=f"http://127.0.0.1:{port}", timeout=5.0
        ) as client:
            async with client.stream("GET", "/api/events") as resp:
                assert resp.status_code == 200

                broker = app_with_fake.state.store.broker

                async def _publish_in_server_loop():
                    await asyncio.sleep(0.2)
                    await broker.publish(publish_event)

                asyncio.run_coroutine_threadsafe(
                    _publish_in_server_loop(), server.server_loop
                )

                async with asyncio.timeout(4.0):
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        payload = line[len("data: "):]
                        if not payload:
                            continue
                        event = json.loads(payload)
                        if event.get("kind") == expected_kind:
                            found = event
                            break
    finally:
        server.should_exit = True
        server_thread.join(timeout=5.0)

    return found


@pytest.mark.asyncio
async def test_entity_updated_broker_event_reaches_sse(app_with_fake):
    """broker.publish({kind: entity_updated, entity_id: ...}) → SSE data:
    frame with matching payload."""
    found = await _run_sse_emit_and_collect(
        app_with_fake,
        {"kind": "entity_updated", "entity_id": "light.lamp"},
        "entity_updated",
    )
    assert found == {"kind": "entity_updated", "entity_id": "light.lamp"}


@pytest.mark.asyncio
async def test_entity_deleted_broker_event_reaches_sse(app_with_fake):
    found = await _run_sse_emit_and_collect(
        app_with_fake,
        {"kind": "entity_deleted", "entity_id": "light.lamp"},
        "entity_deleted",
    )
    assert found == {"kind": "entity_deleted", "entity_id": "light.lamp"}


@pytest.mark.asyncio
async def test_entities_changed_broker_event_reaches_sse(app_with_fake):
    """Broad `entities_changed` event — no entity_id — reaches SSE. Fires on
    every entity-registry refresh so subscribers know to re-query."""
    found = await _run_sse_emit_and_collect(
        app_with_fake,
        {"kind": "entities_changed"},
        "entities_changed",
    )
    assert found == {"kind": "entities_changed"}
