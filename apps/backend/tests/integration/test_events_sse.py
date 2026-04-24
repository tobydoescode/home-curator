"""SSE /api/events integration test.

We need a *real* TCP connection because both Starlette's TestClient and
httpx.ASGITransport buffer the full response body before exposing it —
which means SSE never streams in-process.  Instead we spin uvicorn on an
ephemeral port in a background thread and hit it with httpx.AsyncClient.

Cross-loop coordination: uvicorn runs in its own event loop (thread).
To publish into the broker's queue from the pytest event loop we use
loop.call_soon_threadsafe so the put_nowait runs in the correct loop.
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


@pytest.mark.asyncio
async def test_sse_emits_on_registry_change(app_with_fake):
    """SSE stream delivers a devices_changed event to a connected client."""
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

    received: list[dict] = []
    try:
        async with httpx.AsyncClient(
            base_url=f"http://127.0.0.1:{port}", timeout=5.0
        ) as client:
            async with client.stream("GET", "/api/events") as resp:
                assert resp.status_code == 200

                # Retrieve the broker that lives in the server's event loop.
                broker = app_with_fake.state.store.broker

                async def _publish_in_server_loop():
                    """Coroutine run inside uvicorn's loop after a short delay."""
                    await asyncio.sleep(0.2)
                    await broker.publish({"kind": "devices_changed"})

                # Schedule the publish on uvicorn's event loop so queue ops
                # stay inside the loop that owns the queues.
                asyncio.run_coroutine_threadsafe(
                    _publish_in_server_loop(), server.server_loop
                )

                # Read lines until we get the first data event (or timeout).
                async with asyncio.timeout(4.0):
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            received.append(json.loads(line[len("data: "):]))
                            break
    finally:
        server.should_exit = True
        server_thread.join(timeout=5.0)

    assert received, "SSE stream received no events"
    assert received[0]["kind"] == "devices_changed"
