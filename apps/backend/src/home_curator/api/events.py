import asyncio
import json

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from home_curator.api.deps import AppState, app_state

router = APIRouter(prefix="/api", tags=["events"])


@router.get("/events")
async def events(request: Request, state: AppState = Depends(app_state)):
    """Server-Sent Events stream of registry change notifications.

    Each `message` event carries JSON `{kind}` where kind is
    `devices_changed` or `policies_changed`.
    """
    queue = state.broker.subscribe()

    async def event_source():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=25.0)
                    yield {"event": "message", "data": json.dumps(event)}
                except TimeoutError:
                    yield {"event": "ping", "data": ""}
        finally:
            state.broker.unsubscribe(queue)

    return EventSourceResponse(event_source())
