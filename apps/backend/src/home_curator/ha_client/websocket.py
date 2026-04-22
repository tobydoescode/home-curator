import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

import websockets
from websockets.asyncio.client import ClientConnection, connect

from home_curator.ha_client.base import EventHandler, HAAreaDict, HADeviceDict, RegistryEvent

log = logging.getLogger(__name__)


class WebSocketHAClient:
    def __init__(self, url: str, token: str) -> None:
        self._url = url
        self._token = token
        self._ws: ClientConnection | None = None
        self._msg_id = 1
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._handlers: list[EventHandler] = []
        self._reader_task: asyncio.Task[None] | None = None
        self._entity_index: dict[str, list[dict[str, str]]] = {}

    async def start(self) -> None:
        self._ws = await connect(self._url)
        # auth handshake
        first = json.loads(await self._ws.recv())
        if first.get("type") != "auth_required":
            raise RuntimeError(f"unexpected first message: {first}")
        await self._ws.send(json.dumps({"type": "auth", "access_token": self._token}))
        result = json.loads(await self._ws.recv())
        if result.get("type") != "auth_ok":
            raise RuntimeError(f"auth failed: {result}")
        self._reader_task = asyncio.create_task(self._read_loop())
        # Subscribe to registry change events
        await self._send_cmd({"type": "subscribe_events", "event_type": "device_registry_updated"})
        await self._send_cmd({"type": "subscribe_events", "event_type": "area_registry_updated"})

    async def stop(self) -> None:
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
        if self._ws:
            await self._ws.close()

    async def _send_cmd(self, payload: dict[str, Any]) -> dict[str, Any]:
        assert self._ws
        self._msg_id += 1
        mid = self._msg_id
        payload = {"id": mid, **payload}
        fut: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._pending[mid] = fut
        await self._ws.send(json.dumps(payload))
        return await fut

    async def _read_loop(self) -> None:
        assert self._ws
        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                mid = msg.get("id")
                if mid in self._pending:
                    fut = self._pending.pop(mid)
                    if msg.get("type") == "result" and msg.get("success"):
                        fut.set_result(msg.get("result"))
                    else:
                        fut.set_exception(RuntimeError(f"HA error: {msg}"))
                elif msg.get("type") == "event":
                    event = msg.get("event", {})
                    kind = event.get("event_type")
                    data = event.get("data", {})
                    if kind == "device_registry_updated":
                        self._dispatch({"kind": "device_updated", "device_id": data.get("device_id")})
                    elif kind == "area_registry_updated":
                        self._dispatch({"kind": "area_updated"})
        except asyncio.CancelledError:
            return

    def _dispatch(self, event: RegistryEvent) -> None:
        for h in list(self._handlers):
            try:
                h(event)
            except Exception:
                log.exception("subscriber raised")

    async def get_devices(self) -> list[HADeviceDict]:
        devs = await self._send_cmd({"type": "config/device_registry/list"})
        # Attach entities by calling entity registry
        ents = await self._send_cmd({"type": "config/entity_registry/list"})
        index: dict[str, list[dict[str, str]]] = {}
        for e in ents or []:
            index.setdefault(e["device_id"], []).append({"id": e["entity_id"], "domain": e["entity_id"].split(".")[0]})
        out: list[HADeviceDict] = []
        for d in devs or []:
            out.append({
                "id": d["id"],
                "name": d.get("name_by_user") or d.get("name") or d["id"],
                "name_by_user": d.get("name_by_user"),
                "manufacturer": d.get("manufacturer"),
                "model": d.get("model"),
                "area_id": d.get("area_id"),
                "integration": (d.get("config_entries") or [None])[0],
                "disabled_by": d.get("disabled_by"),
                "identifiers": [list(i) for i in d.get("identifiers", [])],
                "entities": index.get(d["id"], []),
            })
        return out

    async def get_areas(self) -> list[HAAreaDict]:
        res = await self._send_cmd({"type": "config/area_registry/list"})
        return [{"id": a["area_id"], "name": a["name"]} for a in (res or [])]

    async def update_device(self, device_id: str, changes: dict[str, Any]) -> None:
        await self._send_cmd({"type": "config/device_registry/update", "device_id": device_id, **changes})

    def subscribe(self, handler: EventHandler) -> Callable[[], None]:
        self._handlers.append(handler)

        def unsub() -> None:
            if handler in self._handlers:
                self._handlers.remove(handler)

        return unsub
