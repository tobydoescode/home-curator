import asyncio

import pytest

from home_curator.events.broker import EventBroker


@pytest.mark.asyncio
async def test_publish_reaches_all_subscribers():
    broker = EventBroker()
    q1 = broker.subscribe()
    q2 = broker.subscribe()
    await broker.publish({"kind": "devices_changed"})
    assert await asyncio.wait_for(q1.get(), 1) == {"kind": "devices_changed"}
    assert await asyncio.wait_for(q2.get(), 1) == {"kind": "devices_changed"}


@pytest.mark.asyncio
async def test_unsubscribe_stops_delivery():
    broker = EventBroker()
    q = broker.subscribe()
    broker.unsubscribe(q)
    await broker.publish({"kind": "x"})
    # Queue remains empty
    assert q.empty()
