import asyncio
import logging
from typing import Any

log = logging.getLogger(__name__)

# A browser tab that has stopped reading but not yet dropped its TCP
# connection is invisible to us for up to the SSE ping interval. Unbounded
# queues meant its backlog grew for as long as that took, holding every event
# published in the meantime.
#
# These events are notifications, not a log: each one only tells the client
# that something changed, and the client refetches. Dropping the oldest when a
# consumer falls behind therefore costs nothing — the newest event still
# arrives, and it is the one that matters.
MAX_QUEUED_EVENTS = 100


class EventBroker:
    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[dict[str, Any]]] = []

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=MAX_QUEUED_EVENTS)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    async def publish(self, event: dict[str, Any]) -> None:
        for q in list(self._subscribers):
            _put_dropping_oldest(q, event)


def _put_dropping_oldest(
    queue: asyncio.Queue[dict[str, Any]], event: dict[str, Any]
) -> None:
    """Enqueue `event`, discarding the oldest entries if the queue is full.

    Never blocks and never raises: a stalled subscriber must not be able to
    slow down publishing for everyone else, and losing an old notification is
    harmless when a newer one is right behind it.
    """
    while True:
        try:
            queue.put_nowait(event)
            return
        except asyncio.QueueFull:
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:  # pragma: no cover - drained concurrently
                continue
            log.debug("SSE subscriber is not keeping up; dropped an event")
