import pytest

from home_curator.ha_client.fake import FakeHAClient


@pytest.mark.asyncio
async def test_fake_returns_seeded_devices():
    fake = FakeHAClient(
        devices=[
            {
                "id": "d1",
                "name": "lamp",
                "name_by_user": None,
                "manufacturer": "Signify",
                "model": "m",
                "area_id": "living",
                "integration": "hue",
                "disabled_by": None,
                "identifiers": [["hue", "abc"]],
                "entities": [{"id": "light.lamp", "domain": "light"}],
            }
        ],
        areas=[{"id": "living", "name": "Living Room"}],
    )
    devs = await fake.get_devices()
    assert len(devs) == 1
    assert devs[0]["name"] == "lamp"
    areas = await fake.get_areas()
    assert areas[0]["name"] == "Living Room"


@pytest.mark.asyncio
async def test_fake_records_update_calls():
    fake = FakeHAClient(devices=[], areas=[])
    await fake.update_device("d1", {"area_id": "kitchen"})
    assert fake.update_calls == [("d1", {"area_id": "kitchen"})]


@pytest.mark.asyncio
async def test_fake_emits_subscribed_events():
    fake = FakeHAClient(devices=[], areas=[])
    received = []
    fake.subscribe(lambda event: received.append(event))
    await fake.emit({"kind": "device_updated", "device_id": "d1"})
    assert received == [{"kind": "device_updated", "device_id": "d1"}]


@pytest.mark.asyncio
async def test_unsubscribe_stops_delivery_and_is_idempotent():
    fake = FakeHAClient(devices=[], areas=[])
    received = []
    unsub = fake.subscribe(lambda event: received.append(event))
    await fake.emit({"kind": "x"})
    assert len(received) == 1

    unsub()
    await fake.emit({"kind": "y"})
    assert len(received) == 1

    unsub()  # second call must not raise
