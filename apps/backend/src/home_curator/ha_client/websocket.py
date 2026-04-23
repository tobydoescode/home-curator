"""Real Home Assistant websocket client with auto-reconnect."""
import asyncio
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any


def _iso_or_none(v: Any) -> str | None:
    """Accept the shape HA emits for created_at / modified_at.

    HA sends a float (unix seconds) with 0.0 meaning "never set" for
    internal devices (e.g. the Sun entity created before tracking). A
    bare str is treated as already-ISO. Anything else → None.
    """
    if isinstance(v, (int, float)):
        if v <= 0:
            return None
        return datetime.fromtimestamp(v, tz=UTC).isoformat()
    if isinstance(v, str) and v:
        return v
    return None

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed

from home_curator.ha_client.base import (
    EventHandler,
    HAAreaDict,
    HADeviceDict,
    HAEntityDict,
    RegistryEvent,
)

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
        for event_type in ("device_registry_updated", "area_registry_updated", "entity_registry_updated"):
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
                elif kind == "entity_registry_updated":
                    action = data.get("action")
                    entity_id = data.get("entity_id")
                    if action == "remove":
                        self._dispatch({"kind": "entity_deleted", "entity_id": entity_id})
                    else:
                        # create / update — both re-read the entity registry
                        self._dispatch({"kind": "entity_updated", "entity_id": entity_id})

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
        # Map config_entry_id → integration domain (e.g. "hue", "aqara_ble").
        # HA's device registry only carries config_entry ids; we want to show
        # users the human-meaningful integration name instead.
        entries: list[dict[str, Any]] = await self._send_cmd(
            {"type": "config_entries/get"}
        ) or []
        entry_domain: dict[str, str] = {
            e["entry_id"]: e.get("domain", "") for e in entries if e.get("entry_id")
        }

        index: dict[str, list[dict[str, str]]] = {}
        for e in ents:
            entity_id: str = e["entity_id"]
            index.setdefault(e["device_id"], []).append(
                {"id": entity_id, "domain": entity_id.split(".")[0]}
            )
        out: list[HADeviceDict] = []
        for d in devs:
            did: str = d["id"]
            device_entries: list[str] = list(d.get("config_entries") or [])
            primary_entry_id = device_entries[0] if device_entries else None
            out.append({
                "id": did,
                "name": d.get("name_by_user") or d.get("name") or did,
                "name_by_user": d.get("name_by_user"),
                "manufacturer": d.get("manufacturer"),
                "model": d.get("model"),
                "area_id": d.get("area_id"),
                "integration": entry_domain.get(primary_entry_id) if primary_entry_id else None,
                "disabled_by": d.get("disabled_by"),
                "identifiers": [list(i) for i in d.get("identifiers", [])],
                "config_entries": device_entries,
                "entities": index.get(did, []),
                "created_at": _iso_or_none(d.get("created_at")),
                "modified_at": _iso_or_none(d.get("modified_at")),
            })
        return out

    async def get_areas(self) -> list[HAAreaDict]:
        res: list[dict[str, Any]] = await self._send_cmd(
            {"type": "config/area_registry/list"}
        ) or []
        return [{"id": a["area_id"], "name": a["name"]} for a in res]

    async def update_device(self, device_id: str, changes: dict[str, Any]) -> None:
        await self._send_cmd({"type": "config/device_registry/update", "device_id": device_id, **changes})

    async def delete_device(self, device_id: str) -> None:
        """Remove the device by unlinking every config entry that owns it.

        Home Assistant deletes a device once the last config entry is
        removed. Integrations are free to refuse; if any call returns a
        non-success result, `_send_cmd` raises and we propagate that
        error to the caller.

        Not atomic for multi-entry devices: if the first entry removes but
        the second is refused, we raise, leaving the device in HA with
        only the entries we didn't reach. Retry is safe — the
        remove_config_entry call is HA-idempotent — so the caller can
        surface the error and let the user try again.
        """
        # Re-query HA rather than trusting the cache: the cache updates on
        # SSE events, which land *after* HA commits a change. During a bulk
        # delete (looping over device_ids in the API layer) the cache for
        # device N can already be stale by the time we act on it, so
        # trusting it risks sending remove_config_entry for an entry HA
        # just removed.
        devs: list[dict[str, Any]] = await self._send_cmd(
            {"type": "config/device_registry/list"}
        ) or []
        match = next((d for d in devs if d["id"] == device_id), None)
        if match is None:
            raise RuntimeError(f"device {device_id} not found in HA registry")
        entries: list[str] = list(match.get("config_entries") or [])
        if not entries:
            raise RuntimeError(f"device {device_id} has no config entries to remove")
        for entry_id in entries:
            await self._send_cmd({
                "type": "config/device_registry/remove_config_entry",
                "config_entry_id": entry_id,
                "device_id": device_id,
            })

    async def get_entities(self) -> list[HAEntityDict]:
        res: list[dict[str, Any]] = await self._send_cmd(
            {"type": "config/entity_registry/list"}
        ) or []
        out: list[HAEntityDict] = []
        for e in res:
            out.append({
                "entity_id": e["entity_id"],
                "name": e.get("name"),
                "original_name": e.get("original_name"),
                "icon": e.get("icon"),
                "platform": e.get("platform", ""),
                "device_id": e.get("device_id"),
                "area_id": e.get("area_id"),
                "disabled_by": e.get("disabled_by"),
                "hidden_by": e.get("hidden_by"),
                "unique_id": e.get("unique_id"),
                "created_at": _iso_or_none(e.get("created_at")),
                "modified_at": _iso_or_none(e.get("modified_at")),
            })
        return out

    async def update_entity(self, entity_id: str, changes: dict[str, Any]) -> None:
        """Forward a partial entity update through HA's entity_registry/update
        command. Callers pass only changed fields (including `new_entity_id`
        for slug rename) — HA refusal surfaces as a RuntimeError from
        `_send_cmd`.
        """
        await self._send_cmd({
            "type": "config/entity_registry/update",
            "entity_id": entity_id,
            **changes,
        })

    async def delete_entity(self, entity_id: str) -> None:
        """Remove an entity from the HA entity registry.

        HA may refuse if the entity belongs to an active integration that
        expects it; the error bubbles as RuntimeError from `_send_cmd`.
        """
        await self._send_cmd({
            "type": "config/entity_registry/remove",
            "entity_id": entity_id,
        })

    def subscribe(self, handler: EventHandler) -> Callable[[], None]:
        self._handlers.append(handler)

        def unsub() -> None:
            if handler in self._handlers:
                self._handlers.remove(handler)

        return unsub
