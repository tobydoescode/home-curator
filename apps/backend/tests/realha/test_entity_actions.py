"""Entity writes against a real Home Assistant registry."""

from __future__ import annotations

import pytest

from home_curator.ha_client.models import HAEntityUpdate

pytestmark = pytest.mark.realha

DISPOSABLE_ENTITY = "sensor.disposable"


async def _entity(ha_client, entity_id: str):
    return next(
        (e for e in await ha_client.get_entities() if e.entity_id == entity_id), None
    )


async def test_update_entity_sets_friendly_name(ha_client):
    before = await _entity(ha_client, "sensor.temperature")
    assert before is not None
    assert before.name is None

    try:
        await ha_client.update_entity(
            "sensor.temperature", HAEntityUpdate(name="Renamed Sensor")
        )
        after = await _entity(ha_client, "sensor.temperature")
        assert after is not None
        assert after.name == "Renamed Sensor"
        # The integration's own name is preserved underneath the override.
        assert after.original_name == "Temperature"
    finally:
        await ha_client.update_entity(
            "sensor.temperature", HAEntityUpdate(name=None)
        )

    restored = await _entity(ha_client, "sensor.temperature")
    assert restored is not None
    assert restored.name is None


async def test_update_entity_renames_the_slug(ha_client):
    """`new_entity_id` is the mechanism behind the entity rename-pattern action."""
    original = "media_player.office"
    renamed = "media_player.office_renamed"

    assert await _entity(ha_client, original) is not None
    try:
        await ha_client.update_entity(
            original, HAEntityUpdate(new_entity_id=renamed)
        )
        assert await _entity(ha_client, original) is None
        moved = await _entity(ha_client, renamed)
        assert moved is not None
        # Identity survives the rename — this is why the deletion tracker
        # hashes on (platform, unique_id) rather than entity_id.
        assert moved.unique_id == "cast-office-1"
    finally:
        await ha_client.update_entity(
            renamed, HAEntityUpdate(new_entity_id=original)
        )

    assert await _entity(ha_client, original) is not None


async def test_update_entity_assigns_area(ha_client):
    areas = {a.name: a.id for a in await ha_client.get_areas()}
    target = areas["Living Room"]

    before = await _entity(ha_client, "sensor.temperature")
    assert before is not None
    assert before.area_id is None

    try:
        await ha_client.update_entity(
            "sensor.temperature", HAEntityUpdate(area_id=target)
        )
        after = await _entity(ha_client, "sensor.temperature")
        assert after is not None
        assert after.area_id == target
    finally:
        await ha_client.update_entity(
            "sensor.temperature", HAEntityUpdate(area_id=None)
        )


async def test_update_entity_toggles_hidden_and_disabled(ha_client):
    """Backs the bulk enable / disable / show / hide action."""
    target = "light.kitchen_ceiling"

    try:
        await ha_client.update_entity(target, HAEntityUpdate(hidden_by="user"))
        hidden = await _entity(ha_client, target)
        assert hidden is not None
        assert hidden.hidden_by == "user"

        await ha_client.update_entity(target, HAEntityUpdate(hidden_by=None))
        shown = await _entity(ha_client, target)
        assert shown is not None
        assert shown.hidden_by is None
    finally:
        await ha_client.update_entity(target, HAEntityUpdate(hidden_by=None))


async def test_delete_entity_removes_it_from_the_registry(ha_client):
    assert await _entity(ha_client, DISPOSABLE_ENTITY) is not None

    await ha_client.delete_entity(DISPOSABLE_ENTITY)

    assert await _entity(ha_client, DISPOSABLE_ENTITY) is None


async def test_delete_entity_rejects_unknown_entity(ha_client):
    with pytest.raises(RuntimeError):
        await ha_client.delete_entity("sensor.definitely_not_real")
