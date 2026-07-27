import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from home_curator.api.deps import AppState, app_state

router = APIRouter(prefix="/api", tags=["events"])

# Proxies and browsers drop an idle stream, so something has to be sent
# periodically; the disconnect check runs much more often than that.
_PING_SECONDS = 25.0
_DISCONNECT_POLL_SECONDS = 2.0
_APP_STATE_DEPENDENCY = Depends(app_state)


@router.get("/events")
async def events(
    request: Request, state: AppState = _APP_STATE_DEPENDENCY
) -> EventSourceResponse:
    """Server-Sent Events stream of registry change notifications.

    Each `message` event carries JSON `{kind}` where kind is
    `devices_changed` or `policies_changed`.
    """
    queue = state.broker.subscribe()
    waited = 0.0

    async def event_source() -> AsyncIterator[dict[str, str]]:
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    # Poll for disconnection far more often than the keep-alive
                    # ping. Waiting the full ping interval on the queue meant a
                    # client that had gone away was only noticed up to 25s
                    # later, and its queue accumulated the whole time.
                    event = await asyncio.wait_for(
                        queue.get(), timeout=_DISCONNECT_POLL_SECONDS
                    )
                except TimeoutError:
                    waited += _DISCONNECT_POLL_SECONDS
                    if waited < _PING_SECONDS:
                        continue
                    waited = 0.0
                    yield {"event": "ping", "data": ""}
                    continue
                waited = 0.0
                yield {"event": "message", "data": json.dumps(event)}
        finally:
            state.broker.unsubscribe(queue)

    return EventSourceResponse(event_source())
