"""Registry change events, end to end from Home Assistant to our dispatcher.

`WebSocketHAClient` subscribes to `device_registry_updated`,
`area_registry_updated` and `entity_registry_updated` and translates each
into a typed event. The translation reads `data.action` and `data.entity_id`
out of the event payload — shapes that are not documented anywhere, so this
is the only place they are checked.
"""

from __future__ import annotations

import asyncio

import pytest

from home_curator.ha_client.models import (
    DeviceUpdatedEvent,
    EntityDeletedEvent,
    EntityUpdatedEvent,
    HADeviceUpdate,
    HAEntityUpdate,
)

pytestmark = pytest.mark.realha

_EVENT_TIMEOUT_SECONDS = 20


class _Collector:
    """Captures dispatched events and lets a test await a specific type."""

    def __init__(self) -> None:
        self.events: list[object] = []
        self._arrived = asyncio.Event()
        self._loop = asyncio.get_event_loop()

    def __call__(self, event: object) -> None:
        self.events.append(event)
        # Dispatched synchronously from the client's read loop.
        self._loop.call_soon_threadsafe(self._arrived.set)

    async def wait_for(self, event_type: type) -> object:
        deadline = asyncio.get_running_loop().time() + _EVENT_TIMEOUT_SECONDS
        while True:
            match = next((e for e in self.events if isinstance(e, event_type)), None)
            if match is not None:
                return match
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise AssertionError(
                    f"no {event_type.__name__} within {_EVENT_TIMEOUT_SECONDS}s; "
                    f"saw {[type(e).__name__ for e in self.events]}"
                )
            self._arrived.clear()
            try:
                await asyncio.wait_for(self._arrived.wait(), timeout=remaining)
            except TimeoutError:
                continue


async def test_device_update_dispatches_device_updated(ha_client):
    device = next(d for d in await ha_client.get_devices() if d.name == "BadCase")
    collector = _Collector()
    unsub = ha_client.subscribe(collector)

    try:
        await ha_client.update_device(
            device.id, HADeviceUpdate(name_by_user="Event Probe")
        )
        event = await collector.wait_for(DeviceUpdatedEvent)
        assert isinstance(event, DeviceUpdatedEvent)
        # The id is what lets the app refresh narrowly instead of broadly.
        assert event.device_id == device.id
    finally:
        unsub()
        await ha_client.update_device(device.id, HADeviceUpdate(name_by_user=None))


async def test_entity_update_dispatches_entity_updated(ha_client):
    collector = _Collector()
    unsub = ha_client.subscribe(collector)

    try:
        await ha_client.update_entity(
            "sensor.temperature", HAEntityUpdate(name="Event Probe")
        )
        event = await collector.wait_for(EntityUpdatedEvent)
        assert isinstance(event, EntityUpdatedEvent)
        assert event.entity_id == "sensor.temperature"
    finally:
        unsub()
        await ha_client.update_entity(
            "sensor.temperature", HAEntityUpdate(name=None)
        )


async def test_entity_removal_dispatches_entity_deleted(ha_client):
    """Removal must map to `EntityDeletedEvent`, not `EntityUpdatedEvent`.

    The client distinguishes them purely by `data.action == "remove"`.
    """
    # Reserved for this test — deleting a fixture other tests read would
    # couple them through the session-scoped container.
    target = "sensor.disposable_event"
    entities = {e.entity_id for e in await ha_client.get_entities()}
    assert target in entities

    collector = _Collector()
    unsub = ha_client.subscribe(collector)
    try:
        await ha_client.delete_entity(target)
        event = await collector.wait_for(EntityDeletedEvent)
        assert isinstance(event, EntityDeletedEvent)
        assert event.entity_id == target
    finally:
        unsub()
