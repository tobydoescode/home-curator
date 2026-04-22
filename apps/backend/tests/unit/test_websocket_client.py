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
