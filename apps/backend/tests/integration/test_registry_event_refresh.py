"""When HA emits device_registry_updated, the backend must refresh its
registry cache so /api/devices reflects the change immediately — not only
after the 5-minute safety resync loop runs.
"""
import asyncio
import socket
import threading
import time

import httpx
import pytest
import uvicorn


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Server(uvicorn.Server):
    def __init__(self, config: uvicorn.Config) -> None:
        super().__init__(config)
        self.ready = threading.Event()
        self.server_loop: asyncio.AbstractEventLoop | None = None

    def install_signal_handlers(self) -> None:
        pass

    async def startup(self, sockets=None) -> None:
        self.server_loop = asyncio.get_running_loop()
        await super().startup(sockets=sockets)
        self.ready.set()


@pytest.mark.asyncio
async def test_device_rename_propagates_via_registry_event(app_with_fake, fake_ha):
    """Rename a device in the fake HA, emit device_registry_updated, then
    confirm /api/devices returns the new name without waiting for the
    5-minute safety resync."""
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

    assert server.ready.wait(timeout=5.0)
    assert server.server_loop is not None

    try:
        async with httpx.AsyncClient(
            base_url=f"http://127.0.0.1:{port}", timeout=5.0
        ) as client:
            # Baseline: the seeded device d1 is named "living_room_lamp".
            r = await client.get("/api/devices", params={"page": 1, "page_size": 100})
            assert r.status_code == 200
            names = {d["id"]: d["name"] for d in r.json()["devices"]}
            assert names.get("d1") == "living_room_lamp"

            # Change the fake's underlying data, then emit the HA event.
            async def _simulate_rename():
                fake_ha.set_devices([
                    {**d, "name_by_user": "kitchen_light_1"} if d["id"] == "d1" else d
                    for d in [
                        {
                            "id": "d1",
                            "name": "living_room_lamp",
                            "name_by_user": None,
                            "manufacturer": "Signify",
                            "model": "m",
                            "area_id": "living",
                            "integration": "hue",
                            "disabled_by": None,
                            "identifiers": [["hue", "a"]],
                            "entities": [{"id": "light.lamp", "domain": "light"}],
                        },
                        {
                            "id": "d2",
                            "name": "BadCase",
                            "name_by_user": None,
                            "manufacturer": "Aqara",
                            "model": "m",
                            "area_id": None,
                            "integration": "aqara",
                            "disabled_by": None,
                            "identifiers": [["aqara", "b"]],
                            "entities": [],
                        },
                    ]
                ])
                await fake_ha.emit({"kind": "device_updated", "device_id": "d1"})

            asyncio.run_coroutine_threadsafe(
                _simulate_rename(), server.server_loop
            ).result(timeout=2.0)

            # Poll /api/devices for up to 2s waiting for the refresh to land.
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                r = await client.get("/api/devices", params={"page": 1, "page_size": 100})
                names = {d["id"]: d["name"] for d in r.json()["devices"]}
                if names.get("d1") == "kitchen_light_1":
                    break
                await asyncio.sleep(0.05)

            assert names.get("d1") == "kitchen_light_1", (
                "Device rename was not reflected in /api/devices after "
                "device_registry_updated event — cache.refresh() is likely missing "
                "from the event handler path."
            )
    finally:
        server.should_exit = True
        server_thread.join(timeout=5.0)
