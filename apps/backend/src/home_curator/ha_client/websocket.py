"""Real Home Assistant websocket client with auto-reconnect."""
import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed

from home_curator.ha_client.base import EventHandler, HAAreaDict, HADeviceDict, RegistryEvent

log = logging.getLogger(__name__)

# Reverse proxies can introduce multi-second latency spikes on WebSocket
# ping/pong. Default library values (20/20) are too aggressive for self-hosted
# HA setups; 30/60 tolerates blips without dropping the connection.
_PING_INTERVAL = 30
_PING_TIMEOUT = 60

_RECONNECT_BACKOFF_SECONDS = (1, 2, 5, 10, 30)


class WebSocketHAClient:
    def __init__(self, url: str, token: str) -> None:
        self._url = url
        self._token = token
        self._ws: ClientConnection | None = None
        self._msg_id = 1
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._handlers: list[EventHandler] = []
        self._supervisor_task: asyncio.Task[None] | None = None
        self._ready = asyncio.Event()
        self._stopping = False

    async def start(self) -> None:
        """Establish the initial connection and start the supervisor loop.

        After `start()` returns, the client has authenticated and subscribed.
        If the connection drops later, the supervisor reconnects transparently.
        """
        await self._connect_and_handshake()
        self._supervisor_task = asyncio.create_task(self._supervise())

    async def stop(self) -> None:
        self._stopping = True
        if self._supervisor_task:
            self._supervisor_task.cancel()
            try:
                await self._supervisor_task
            except asyncio.CancelledError:
                pass
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass

    async def _connect_and_handshake(self) -> None:
        """Open the WebSocket, auth, and re-subscribe to registry events.

        Shared between initial `start()` and every reconnect attempt. Does
        not return until the handshake + subscriptions are acknowledged. The
        subscriptions use direct `recv()` (not `_send_cmd`) because the
        reader loop isn't running yet at this point; the reader starts in
        `_supervise` after this returns.
        """
        self._ready.clear()
        # HA's registry list responses can exceed the default 1 MiB frame
        # limit on instances with many entities; we enable permessage-deflate
        # (5–10× smaller on the wire) and lift the max frame cap.
        ws = await connect(
            self._url,
            max_size=None,
            compression="deflate",
            ping_interval=_PING_INTERVAL,
            ping_timeout=_PING_TIMEOUT,
        )
        self._ws = ws

        first = json.loads(await ws.recv())
        if first.get("type") != "auth_required":
            await ws.close()
            raise RuntimeError(f"unexpected first message: {first}")
        await ws.send(json.dumps({"type": "auth", "access_token": self._token}))
        result = json.loads(await ws.recv())
        if result.get("type") != "auth_ok":
            await ws.close()
            raise RuntimeError(f"auth failed: {result}")

        # Re-subscribe to registry change events on every (re)connection.
        # Read until we see the matching result id — HA may interleave events
        # or other server-initiated messages with command responses.
        for event_type in ("device_registry_updated", "area_registry_updated"):
            self._msg_id += 1
            mid = self._msg_id
            await ws.send(
                json.dumps({"id": mid, "type": "subscribe_events", "event_type": event_type})
            )
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("id") == mid and msg.get("type") == "result":
                    if not msg.get("success"):
                        await ws.close()
                        raise RuntimeError(f"subscribe_events failed: {msg}")
                    break
                # Any other message (event, different id) is discarded here;
                # the reader loop will pick up subsequent ones cleanly.

        self._ready.set()

    async def _supervise(self) -> None:
        """Run the read loop forever, reconnecting with backoff on drops."""
        attempt = 0
        while not self._stopping:
            try:
                await self._read_loop()
            except asyncio.CancelledError:
                raise
            except ConnectionClosed as e:
                log.warning("HA WebSocket closed (%s); will reconnect", e)
            except Exception:
                log.exception("HA WebSocket read loop crashed; will reconnect")

            if self._stopping:
                return

            # Fail any in-flight requests so callers don't hang forever.
            self._fail_pending(RuntimeError("HA WebSocket disconnected"))

            delay = _RECONNECT_BACKOFF_SECONDS[
                min(attempt, len(_RECONNECT_BACKOFF_SECONDS) - 1)
            ]
            log.info("Reconnecting to HA in %ds (attempt %d)", delay, attempt + 1)
            try:
                await asyncio.sleep(delay)
                await self._connect_and_handshake()
                attempt = 0
                log.info("HA WebSocket reconnected")
                # Tell subscribers so they can refresh caches post-reconnect.
                self._dispatch({"kind": "reconnected"})
            except asyncio.CancelledError:
                raise
            except Exception:
                attempt += 1
                log.exception("Reconnect attempt %d failed", attempt)

    def _fail_pending(self, exc: BaseException) -> None:
        for mid, fut in list(self._pending.items()):
            if not fut.done():
                fut.set_exception(exc)
            self._pending.pop(mid, None)

    async def _send_cmd(self, payload: dict[str, Any]) -> Any:
        assert self._ws is not None
        self._msg_id += 1
        mid = self._msg_id
        payload = {"id": mid, **payload}
        fut: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._pending[mid] = fut
        try:
            await self._ws.send(json.dumps(payload))
        except Exception:
            self._pending.pop(mid, None)
            raise
        return await fut

    async def _read_loop(self) -> None:
        assert self._ws is not None
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

    def _dispatch(self, event: RegistryEvent) -> None:
        for h in list(self._handlers):
            try:
                h(event)
            except Exception:
                log.exception("subscriber raised")

    async def get_devices(self) -> list[HADeviceDict]:
        devs: list[dict[str, Any]] = await self._send_cmd(
            {"type": "config/device_registry/list"}
        ) or []
        ents: list[dict[str, Any]] = await self._send_cmd(
            {"type": "config/entity_registry/list"}
        ) or []
        index: dict[str, list[dict[str, str]]] = {}
        for e in ents:
            entity_id: str = e["entity_id"]
            index.setdefault(e["device_id"], []).append(
                {"id": entity_id, "domain": entity_id.split(".")[0]}
            )
        out: list[HADeviceDict] = []
        for d in devs:
            did: str = d["id"]
            out.append({
                "id": did,
                "name": d.get("name_by_user") or d.get("name") or did,
                "name_by_user": d.get("name_by_user"),
                "manufacturer": d.get("manufacturer"),
                "model": d.get("model"),
                "area_id": d.get("area_id"),
                "integration": (d.get("config_entries") or [None])[0],
                "disabled_by": d.get("disabled_by"),
                "identifiers": [list(i) for i in d.get("identifiers", [])],
                "entities": index.get(did, []),
                "created_at": d.get("created_at"),
                "modified_at": d.get("modified_at"),
            })
        return out

    async def get_areas(self) -> list[HAAreaDict]:
        res: list[dict[str, Any]] = await self._send_cmd(
            {"type": "config/area_registry/list"}
        ) or []
        return [{"id": a["area_id"], "name": a["name"]} for a in res]

    async def update_device(self, device_id: str, changes: dict[str, Any]) -> None:
        await self._send_cmd({"type": "config/device_registry/update", "device_id": device_id, **changes})

    def subscribe(self, handler: EventHandler) -> Callable[[], None]:
        self._handlers.append(handler)

        def unsub() -> None:
            if handler in self._handlers:
                self._handlers.remove(handler)

        return unsub
