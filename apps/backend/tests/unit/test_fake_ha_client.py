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
    assert devs[0]["name"] == "lamp"  # type: ignore[typeddict-item]
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


@pytest.mark.asyncio
async def test_fake_delete_device_removes_from_store_and_records_call():
    from home_curator.ha_client.fake import FakeHAClient

    ha = FakeHAClient(
        devices=[
            {"id": "d1", "name": "a", "config_entries": ["e1"]},
            {"id": "d2", "name": "b", "config_entries": ["e2"]},
        ],
        areas=[],
    )

    await ha.delete_device("d1")

    assert ha.delete_calls == ["d1"]
    remaining = await ha.get_devices()
    assert [d["id"] for d in remaining] == ["d2"]


@pytest.mark.asyncio
async def test_fake_returns_seeded_entities():
    fake = FakeHAClient(
        devices=[],
        areas=[],
        entities=[
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
                "created_at": None,
                "modified_at": None,
            }
        ],
    )
    ents = await fake.get_entities()
    assert len(ents) == 1
    assert ents[0]["entity_id"] == "light.kitchen_lamp"
    assert ents[0]["platform"] == "hue"  # type: ignore[typeddict-item]


@pytest.mark.asyncio
async def test_fake_records_update_entity_calls_and_mutates_store():
    fake = FakeHAClient(
        devices=[],
        areas=[],
        entities=[
            {
                "entity_id": "light.lamp",
                "name": None,
                "original_name": "Lamp",
                "platform": "hue",
                "device_id": "d1",
                "area_id": None,
                "disabled_by": None,
                "hidden_by": None,
                "unique_id": "x",
            }
        ],
    )
    await fake.update_entity("light.lamp", {"name": "Kitchen Lamp"})
    assert fake.update_entity_calls == [("light.lamp", {"name": "Kitchen Lamp"})]
    ents = await fake.get_entities()
    assert ents[0]["name"] == "Kitchen Lamp"  # type: ignore[typeddict-item]


@pytest.mark.asyncio
async def test_fake_delete_entity_removes_from_store_and_records_call():
    fake = FakeHAClient(
        devices=[],
        areas=[],
        entities=[
            {"entity_id": "light.a", "platform": "hue", "device_id": None},
            {"entity_id": "light.b", "platform": "hue", "device_id": None},
        ],
    )
    await fake.delete_entity("light.a")
    assert fake.delete_entity_calls == ["light.a"]
    ents = await fake.get_entities()
    assert [e["entity_id"] for e in ents] == ["light.b"]


@pytest.mark.asyncio
async def test_fake_emits_entity_events_to_subscribers():
    fake = FakeHAClient(devices=[], areas=[], entities=[])
    received: list[dict] = []
    fake.subscribe(lambda event: received.append(event))
    await fake.emit({"kind": "entity_updated", "entity_id": "light.lamp"})
    await fake.emit({"kind": "entity_deleted", "entity_id": "light.lamp"})
    assert received == [
        {"kind": "entity_updated", "entity_id": "light.lamp"},
        {"kind": "entity_deleted", "entity_id": "light.lamp"},
    ]
