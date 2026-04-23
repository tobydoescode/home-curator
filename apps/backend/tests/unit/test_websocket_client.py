import asyncio
import json

import pytest
import websockets

from home_curator.ha_client.websocket import WebSocketHAClient

HA_AUTH_OK = {"type": "auth_ok", "ha_version": "2026.4.0"}
HA_AUTH_REQUIRED = {"type": "auth_required", "ha_version": "2026.4.0"}


async def _fake_ha(ws):
    # Expect auth
    await ws.send(json.dumps(HA_AUTH_REQUIRED))
    msg = json.loads(await ws.recv())
    assert msg == {"type": "auth", "access_token": "tok"}
    await ws.send(json.dumps(HA_AUTH_OK))

    # Handle subsequent messages
    async for raw in ws:
        msg = json.loads(raw)
        if msg.get("type") == "config/device_registry/list":
            await ws.send(json.dumps({"id": msg["id"], "type": "result", "success": True, "result": [
                {"id": "d1", "name": "lamp", "area_id": None, "disabled_by": None,
                 "manufacturer": None, "model": None, "name_by_user": None,
                 "identifiers": [["hue", "x"]], "entry_type": None, "config_entries": []}
            ]}))
        elif msg.get("type") == "config/area_registry/list":
            await ws.send(json.dumps({"id": msg["id"], "type": "result", "success": True, "result": [
                {"area_id": "living", "name": "Living Room"}
            ]}))
        elif msg.get("type") == "config/entity_registry/list":
            await ws.send(json.dumps({"id": msg["id"], "type": "result", "success": True, "result": [
                {"entity_id": "light.lamp", "device_id": "d1", "platform": "hue"}
            ]}))
        elif msg.get("type") == "config_entries/get":
            await ws.send(json.dumps({"id": msg["id"], "type": "result", "success": True, "result": [
                {"entry_id": "e1", "domain": "hue"}
            ]}))
        elif msg.get("type") == "subscribe_events":
            await ws.send(json.dumps({"id": msg["id"], "type": "result", "success": True, "result": None}))


@pytest.mark.asyncio
async def test_end_to_end_get_devices():
    async with websockets.serve(_fake_ha, "localhost", 0) as server:
        port = server.sockets[0].getsockname()[1]
        client = WebSocketHAClient(url=f"ws://localhost:{port}", token="tok")
        await client.start()
        try:
            devs = await client.get_devices()
            assert len(devs) == 1
            assert devs[0]["id"] == "d1"
            areas = await client.get_areas()
            assert areas[0]["name"] == "Living Room"
        finally:
            await client.stop()


@pytest.mark.asyncio
async def test_reconnects_and_emits_reconnected_event(monkeypatch):
    """Force the read loop to see a broken connection, then verify the
    supervisor reconnects against the same fake HA and emits a 'reconnected'
    event that subscribers receive."""

    # Collapse the backoff table so the test isn't slow.
    from home_curator.ha_client import websocket as ws_mod

    monkeypatch.setattr(ws_mod, "_RECONNECT_BACKOFF_SECONDS", (0,))

    async with websockets.serve(_fake_ha, "localhost", 0) as server:
        port = server.sockets[0].getsockname()[1]
        client = WebSocketHAClient(url=f"ws://localhost:{port}", token="tok")
        await client.start()

        events: list[dict] = []
        client.subscribe(lambda e: events.append(e))

        try:
            # Slam the WS closed from the client side — mimics keepalive
            # timeout, network drop, etc.
            assert client._ws is not None
            await client._ws.close(code=1011, reason="simulated")

            # Wait up to 3s for the supervisor to reconnect + emit.
            for _ in range(30):
                if any(e.get("kind") == "reconnected" for e in events):
                    break
                await asyncio.sleep(0.1)
            assert any(e.get("kind") == "reconnected" for e in events), (
                f"no reconnect event observed; got {events}"
            )

            # Post-reconnect the client is usable again.
            areas = await client.get_areas()
            assert areas[0]["name"] == "Living Room"
        finally:
            await client.stop()
