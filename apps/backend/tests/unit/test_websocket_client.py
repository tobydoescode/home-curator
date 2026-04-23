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


@pytest.mark.asyncio
async def test_delete_device_removes_each_config_entry():
    # Fake HA records remove_config_entry calls and responds success.
    calls: list[dict] = []

    async def _fake_ha_with_delete(ws):
        await ws.send(json.dumps(HA_AUTH_REQUIRED))
        msg = json.loads(await ws.recv())
        assert msg == {"type": "auth", "access_token": "tok"}
        await ws.send(json.dumps(HA_AUTH_OK))

        async for raw in ws:
            msg = json.loads(raw)
            if msg.get("type") == "config/device_registry/list":
                await ws.send(json.dumps({"id": msg["id"], "type": "result", "success": True, "result": [
                    {"id": "d1", "name": "lamp", "area_id": None, "disabled_by": None,
                     "manufacturer": None, "model": None, "name_by_user": None,
                     "identifiers": [["hue", "x"]], "entry_type": None,
                     "config_entries": ["e1", "e2"]}
                ]}))
            elif msg.get("type") == "config/entity_registry/list":
                await ws.send(json.dumps({"id": msg["id"], "type": "result", "success": True, "result": []}))
            elif msg.get("type") == "config_entries/get":
                await ws.send(json.dumps({"id": msg["id"], "type": "result", "success": True, "result": [
                    {"entry_id": "e1", "domain": "hue"},
                ]}))
            elif msg.get("type") == "subscribe_events":
                await ws.send(json.dumps({"id": msg["id"], "type": "result", "success": True, "result": None}))
            elif msg.get("type") == "config/device_registry/remove_config_entry":
                calls.append(msg)
                await ws.send(json.dumps({"id": msg["id"], "type": "result", "success": True, "result": None}))

    async with websockets.serve(_fake_ha_with_delete, "localhost", 0) as server:
        port = server.sockets[0].getsockname()[1]
        client = WebSocketHAClient(url=f"ws://localhost:{port}", token="tok")
        await client.start()
        try:
            await client.delete_device("d1")
        finally:
            await client.stop()

    types = [c["type"] for c in calls]
    entry_ids = [c["config_entry_id"] for c in calls]
    device_ids = [c["device_id"] for c in calls]
    assert types == ["config/device_registry/remove_config_entry"] * 2
    assert entry_ids == ["e1", "e2"]
    assert device_ids == ["d1", "d1"]


@pytest.mark.asyncio
async def test_get_entities_normalizes_payload():
    async def _fake(ws):
        await ws.send(json.dumps(HA_AUTH_REQUIRED))
        msg = json.loads(await ws.recv())
        assert msg == {"type": "auth", "access_token": "tok"}
        await ws.send(json.dumps(HA_AUTH_OK))
        async for raw in ws:
            msg = json.loads(raw)
            if msg.get("type") == "subscribe_events":
                await ws.send(json.dumps({"id": msg["id"], "type": "result", "success": True, "result": None}))
            elif msg.get("type") == "config/entity_registry/list":
                await ws.send(json.dumps({
                    "id": msg["id"], "type": "result", "success": True,
                    "result": [
                        {
                            "entity_id": "light.kitchen_lamp",
                            "name": "Kitchen Lamp",
                            "original_name": "Philips Hue Bulb",
                            "icon": None,
                            "platform": "hue",
                            "device_id": "d1",
                            "area_id": "kitchen",
                            "disabled_by": None,
                            "hidden_by": None,
                            "unique_id": "hue:abc",
                            "created_at": 1700000000,
                            "modified_at": None,
                        }
                    ],
                }))

    async with websockets.serve(_fake, "localhost", 0) as server:
        port = server.sockets[0].getsockname()[1]
        client = WebSocketHAClient(url=f"ws://localhost:{port}", token="tok")
        await client.start()
        try:
            ents = await client.get_entities()
        finally:
            await client.stop()

    assert len(ents) == 1
    e = ents[0]
    assert e["entity_id"] == "light.kitchen_lamp"
    assert e["platform"] == "hue"
    assert e["device_id"] == "d1"
    assert e["unique_id"] == "hue:abc"
    # epoch-seconds → ISO normalization
    assert isinstance(e["created_at"], str) and e["created_at"].startswith("20")
    assert e["modified_at"] is None


@pytest.mark.asyncio
async def test_update_entity_forwards_changes():
    calls: list[dict] = []

    async def _fake(ws):
        await ws.send(json.dumps(HA_AUTH_REQUIRED))
        msg = json.loads(await ws.recv())
        await ws.send(json.dumps(HA_AUTH_OK))
        async for raw in ws:
            msg = json.loads(raw)
            if msg.get("type") == "subscribe_events":
                await ws.send(json.dumps({"id": msg["id"], "type": "result", "success": True, "result": None}))
            elif msg.get("type") == "config/entity_registry/update":
                calls.append(msg)
                await ws.send(json.dumps({"id": msg["id"], "type": "result", "success": True, "result": None}))

    async with websockets.serve(_fake, "localhost", 0) as server:
        port = server.sockets[0].getsockname()[1]
        client = WebSocketHAClient(url=f"ws://localhost:{port}", token="tok")
        await client.start()
        try:
            await client.update_entity(
                "light.lamp",
                {"name": "Kitchen Lamp", "new_entity_id": "light.kitchen_lamp"},
            )
        finally:
            await client.stop()

    assert len(calls) == 1
    c = calls[0]
    assert c["type"] == "config/entity_registry/update"
    assert c["entity_id"] == "light.lamp"
    assert c["name"] == "Kitchen Lamp"
    assert c["new_entity_id"] == "light.kitchen_lamp"


@pytest.mark.asyncio
async def test_delete_entity_sends_remove_command():
    calls: list[dict] = []

    async def _fake(ws):
        await ws.send(json.dumps(HA_AUTH_REQUIRED))
        msg = json.loads(await ws.recv())
        await ws.send(json.dumps(HA_AUTH_OK))
        async for raw in ws:
            msg = json.loads(raw)
            if msg.get("type") == "subscribe_events":
                await ws.send(json.dumps({"id": msg["id"], "type": "result", "success": True, "result": None}))
            elif msg.get("type") == "config/entity_registry/remove":
                calls.append(msg)
                await ws.send(json.dumps({"id": msg["id"], "type": "result", "success": True, "result": None}))

    async with websockets.serve(_fake, "localhost", 0) as server:
        port = server.sockets[0].getsockname()[1]
        client = WebSocketHAClient(url=f"ws://localhost:{port}", token="tok")
        await client.start()
        try:
            await client.delete_entity("light.lamp")
        finally:
            await client.stop()

    assert calls == [{"id": calls[0]["id"], "type": "config/entity_registry/remove", "entity_id": "light.lamp"}]


@pytest.mark.asyncio
async def test_entity_registry_updated_dispatches_updated_and_deleted():
    """Two server-pushed events: an update and a remove. Subscriber sees
    entity_updated first, then entity_deleted."""
    events: list[dict] = []

    async def _fake(ws):
        await ws.send(json.dumps(HA_AUTH_REQUIRED))
        msg = json.loads(await ws.recv())
        await ws.send(json.dumps(HA_AUTH_OK))
        # Ack each subscribe_events by message id.
        sub_acked = 0
        async for raw in ws:
            msg = json.loads(raw)
            if msg.get("type") == "subscribe_events":
                await ws.send(json.dumps({"id": msg["id"], "type": "result", "success": True, "result": None}))
                sub_acked += 1
                # After the third sub ack (devices/areas/entities) push events.
                if sub_acked == 3:
                    await ws.send(json.dumps({
                        "id": 1, "type": "event",
                        "event": {
                            "event_type": "entity_registry_updated",
                            "data": {"action": "update", "entity_id": "light.a"},
                        },
                    }))
                    await ws.send(json.dumps({
                        "id": 1, "type": "event",
                        "event": {
                            "event_type": "entity_registry_updated",
                            "data": {"action": "remove", "entity_id": "light.a"},
                        },
                    }))

    async with websockets.serve(_fake, "localhost", 0) as server:
        port = server.sockets[0].getsockname()[1]
        client = WebSocketHAClient(url=f"ws://localhost:{port}", token="tok")
        await client.start()
        client.subscribe(lambda e: events.append(e))
        try:
            for _ in range(30):
                if len(events) >= 2:
                    break
                await asyncio.sleep(0.05)
        finally:
            await client.stop()

    kinds = [e["kind"] for e in events]
    assert "entity_updated" in kinds
    assert "entity_deleted" in kinds
    updated = next(e for e in events if e["kind"] == "entity_updated")
    deleted = next(e for e in events if e["kind"] == "entity_deleted")
    assert updated["entity_id"] == "light.a"
    assert deleted["entity_id"] == "light.a"
