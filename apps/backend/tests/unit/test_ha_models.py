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
