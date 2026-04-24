import pytest
from pydantic import ValidationError

from home_curator.ha_client.models import HAArea


def test_ha_area_requires_id_and_name():
    with pytest.raises(ValidationError):
        HAArea(name="Kitchen")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        HAArea(id="kitchen")  # type: ignore[call-arg]


def test_ha_area_accepts_valid_payload():
    a = HAArea(id="kitchen", name="Kitchen")
    assert a.id == "kitchen"
    assert a.name == "Kitchen"


def test_ha_area_is_frozen():
    a = HAArea(id="kitchen", name="Kitchen")
    with pytest.raises(ValidationError):
        a.name = "Lounge"  # type: ignore[misc]


def test_ha_area_ignores_extra_fields():
    a = HAArea.model_validate({"id": "kitchen", "name": "Kitchen", "aliases": ["x"]})
    assert not hasattr(a, "aliases")


from home_curator.ha_client.models import HADeviceEntityRef


def test_ha_device_entity_ref_requires_id_and_domain():
    with pytest.raises(ValidationError):
        HADeviceEntityRef(id="light.lamp")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        HADeviceEntityRef(domain="light")  # type: ignore[call-arg]


def test_ha_device_entity_ref_accepts_valid():
    r = HADeviceEntityRef(id="light.lamp", domain="light")
    assert r.id == "light.lamp"
    assert r.domain == "light"


from home_curator.ha_client.models import HADevice


def test_ha_device_requires_id():
    with pytest.raises(ValidationError):
        HADevice()  # type: ignore[call-arg]


def test_ha_device_minimum_valid_payload():
    d = HADevice(id="d1")
    assert d.id == "d1"
    assert d.name is None
    assert d.identifiers == []
    assert d.config_entries == []
    assert d.entities == []


def test_ha_device_full_payload():
    d = HADevice.model_validate({
        "id": "d1",
        "name": "Lamp",
        "name_by_user": "Kitchen Lamp",
        "manufacturer": "Signify",
        "model": "Hue White",
        "area_id": "kitchen",
        "integration": "hue",
        "disabled_by": None,
        "identifiers": [["hue", "abc"]],
        "config_entries": ["entry-1"],
        "entities": [{"id": "light.lamp", "domain": "light"}],
        "created_at": "2026-04-01T00:00:00Z",
        "modified_at": None,
    })
    assert d.name_by_user == "Kitchen Lamp"
    assert d.entities[0].id == "light.lamp"
    assert d.entities[0].domain == "light"


def test_ha_device_ignores_extra_fields():
    d = HADevice.model_validate({"id": "d1", "new_ha_field": 42})
    assert not hasattr(d, "new_ha_field")


from home_curator.ha_client.models import HAEntity


def test_ha_entity_requires_entity_id():
    with pytest.raises(ValidationError):
        HAEntity()  # type: ignore[call-arg]


def test_ha_entity_minimum_valid_payload():
    e = HAEntity(entity_id="light.lamp")
    assert e.entity_id == "light.lamp"
    assert e.name is None
    assert e.platform == ""


def test_ha_entity_full_payload():
    e = HAEntity.model_validate({
        "entity_id": "light.lamp",
        "name": "Lamp",
        "original_name": "Hue light",
        "icon": "mdi:lamp",
        "platform": "hue",
        "device_id": "d1",
        "area_id": "kitchen",
        "disabled_by": None,
        "hidden_by": None,
        "unique_id": "hue:abc",
        "created_at": "2026-04-01T00:00:00Z",
        "modified_at": None,
    })
    assert e.platform == "hue"
    assert e.unique_id == "hue:abc"


def test_ha_entity_ignores_extra_fields():
    e = HAEntity.model_validate({"entity_id": "light.lamp", "new_field": 1})
    assert not hasattr(e, "new_field")


from home_curator.ha_client.models import HADeviceUpdate, HAEntityUpdate


def test_ha_device_update_unset_fields_absent_from_dump():
    u = HADeviceUpdate(area_id="kitchen")
    assert u.model_dump(exclude_unset=True) == {"area_id": "kitchen"}


def test_ha_device_update_explicit_none_is_clear():
    u = HADeviceUpdate(area_id=None)
    # Explicitly-set None means "clear the field" and must be sent.
    assert u.model_dump(exclude_unset=True) == {"area_id": None}


def test_ha_device_update_empty_dump_is_empty():
    u = HADeviceUpdate()
    assert u.model_dump(exclude_unset=True) == {}


def test_ha_device_update_forbids_extra_fields():
    with pytest.raises(ValidationError):
        HADeviceUpdate(unknown_field="x")  # type: ignore[call-arg]


def test_ha_entity_update_multiple_fields():
    u = HAEntityUpdate(name="Kitchen Lamp", new_entity_id="light.kitchen_lamp")
    assert u.model_dump(exclude_unset=True) == {
        "name": "Kitchen Lamp",
        "new_entity_id": "light.kitchen_lamp",
    }


def test_ha_entity_update_forbids_extra_fields():
    with pytest.raises(ValidationError):
        HAEntityUpdate(bogus=True)  # type: ignore[call-arg]


from pydantic import TypeAdapter

from home_curator.ha_client.models import (
    AreaUpdatedEvent,
    DeviceUpdatedEvent,
    EntityDeletedEvent,
    EntityUpdatedEvent,
    HAEvent,
    ReconnectedEvent,
)


def test_event_discriminator_parses_each_variant():
    adapter = TypeAdapter(HAEvent)
    assert isinstance(
        adapter.validate_python({"kind": "reconnected"}), ReconnectedEvent
    )
    assert isinstance(
        adapter.validate_python({"kind": "area_updated"}), AreaUpdatedEvent
    )
    assert isinstance(
        adapter.validate_python({"kind": "device_updated", "device_id": "d1"}),
        DeviceUpdatedEvent,
    )
    assert isinstance(
        adapter.validate_python({"kind": "entity_updated", "entity_id": "e1"}),
        EntityUpdatedEvent,
    )
    assert isinstance(
        adapter.validate_python({"kind": "entity_deleted", "entity_id": "e1"}),
        EntityDeletedEvent,
    )


def test_event_unknown_kind_rejected():
    with pytest.raises(ValidationError):
        TypeAdapter(HAEvent).validate_python({"kind": "mystery"})


def test_device_updated_event_allows_none_device_id():
    # HA's device_registry_updated event may arrive without a device_id (broad
    # registry change). Preserving the None case keeps current broad-refresh
    # behavior in on_event.
    e = DeviceUpdatedEvent()
    assert e.device_id is None
    e = DeviceUpdatedEvent(device_id="d1")
    assert e.device_id == "d1"


def test_entity_events_allow_none_entity_id():
    # Broad entity_registry_updated events may arrive without an entity_id.
    # Preserving the None case keeps current broad-refresh behavior in
    # _refresh_and_publish_entity (which still triggers entities_changed).
    e = EntityUpdatedEvent()
    assert e.entity_id is None
    d = EntityDeletedEvent()
    assert d.entity_id is None
    # And they still accept specific ids.
    assert EntityUpdatedEvent(entity_id="e1").entity_id == "e1"
    assert EntityDeletedEvent(entity_id="e1").entity_id == "e1"


def test_events_are_frozen():
    e = DeviceUpdatedEvent(device_id="d1")
    with pytest.raises(ValidationError):
        e.device_id = "d2"  # type: ignore[misc]
