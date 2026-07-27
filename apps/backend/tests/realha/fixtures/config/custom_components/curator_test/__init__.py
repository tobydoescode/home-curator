"""Deterministic device / entity / area fixtures for Home Curator's real-HA tests.

This integration exists only to populate a throwaway Home Assistant instance
with a known registry shape, so the real `WebSocketHAClient` can be exercised
against real HA rather than against `FakeHAClient`.

The data deliberately mirrors the `fake_ha` fixture in
`tests/integration/conftest.py` so the same expectations can be asserted
against both. One field cannot be mirrored: a device's `integration` is
derived by Home Assistant from its config entry's domain, so every device
here reports `curator_test` rather than `hue` / `aqara`. Entity `platform`
*is* free-form and is set to the same values the fake uses.

Entities are created directly in the entity registry rather than through a
platform. Home Curator only ever reads the registry, so backing entity
objects would add moving parts without adding coverage.

Two config entries are created. `DEVICE_MULTI_ENTRY` is deliberately linked
to both so the `delete_device` unlink path — which walks every config entry
on a device — has something real to walk.
"""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

DOMAIN = "curator_test"

SLOT_PRIMARY = "primary"
SLOT_SECONDARY = "secondary"

# Identifiers are stable across runs so tests can address fixtures by name.
DEVICE_LAMP = "d1"
DEVICE_BAD_CASE = "d2"
DEVICE_MULTI_ENTRY = "d3"

AREA_LIVING_ROOM = "Living Room"
AREA_KITCHEN = "Kitchen"
AREA_GARAGE = "Garage"

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Kick off both config entries when the integration is listed in YAML."""
    if DOMAIN not in config:
        return True
    for slot in (SLOT_PRIMARY, SLOT_SECONDARY):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={"slot": slot},
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Populate the registries.

    The secondary entry only attaches itself to the multi-entry device; all
    other fixture data belongs to the primary entry.
    """
    device_registry = dr.async_get(hass)

    if entry.data.get("slot") == SLOT_SECONDARY:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, DEVICE_MULTI_ENTRY)},
            manufacturer="Curator",
            model="multi-entry",
            name="multi_entry_device",
        )
        return True

    area_registry = ar.async_get(hass)
    entity_registry = er.async_get(hass)

    areas = {
        name: _ensure_area(area_registry, name)
        for name in (AREA_LIVING_ROOM, AREA_KITCHEN, AREA_GARAGE)
    }

    lamp = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, DEVICE_LAMP)},
        manufacturer="Signify",
        model="m",
        name="living_room_lamp",
    )
    device_registry.async_update_device(lamp.id, area_id=areas[AREA_LIVING_ROOM])

    # No area — exercises the missing_area rule and the "unassigned sorts
    # last" ordering. Name is deliberately not snake_case.
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, DEVICE_BAD_CASE)},
        manufacturer="Aqara",
        model="m",
        name="BadCase",
    )

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, DEVICE_MULTI_ENTRY)},
        manufacturer="Curator",
        model="multi-entry",
        name="multi_entry_device",
    )

    # Owned by the lamp device, no own area — resolves its area through the
    # device, which is the lenient entity_missing_area path.
    _ensure_entity(
        entity_registry,
        domain="light",
        platform="hue",
        unique_id="hue-lamp-1",
        object_id="lamp",
        config_entry=entry,
        device_id=lamp.id,
        original_name="Living Room Lamp",
    )

    # Standalone, user-renamed, own area.
    _ensure_entity(
        entity_registry,
        domain="light",
        platform="mqtt",
        unique_id="mqtt-kc-1",
        object_id="kitchen_ceiling",
        config_entry=entry,
        area_id=areas[AREA_KITCHEN],
        original_name="Ceiling Light",
        name="Kitchen Ceiling",
    )

    _ensure_entity(
        entity_registry,
        domain="sensor",
        platform="aqara",
        unique_id="aqara-temp-1",
        object_id="temperature",
        config_entry=entry,
        original_name="Temperature",
    )

    _ensure_entity(
        entity_registry,
        domain="switch",
        platform="zwave_js",
        unique_id="zwave-gd-1",
        object_id="garage_door",
        config_entry=entry,
        area_id=areas[AREA_GARAGE],
        original_name="Switch",
        name="Garage Door",
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    _ensure_entity(
        entity_registry,
        domain="binary_sensor",
        platform="mqtt",
        unique_id="mqtt-motion-1",
        object_id="kitchen_motion",
        config_entry=entry,
        area_id=areas[AREA_KITCHEN],
        original_name="Motion",
        hidden_by=er.RegistryEntryHider.USER,
    )

    # Fully unassigned: no device, no area, no original_name.
    _ensure_entity(
        entity_registry,
        domain="media_player",
        platform="cast",
        unique_id="cast-office-1",
        object_id="office",
        config_entry=entry,
        name="Office Speaker",
    )

    # Reserved for the destructive tests. Each gets its own so that deleting
    # one cannot invalidate a fixture another test asserts against — the
    # container is shared for the whole session.
    _ensure_entity(
        entity_registry,
        domain="sensor",
        platform="curator_test",
        unique_id="disposable-1",
        object_id="disposable",
        config_entry=entry,
        original_name="Disposable",
    )
    _ensure_entity(
        entity_registry,
        domain="sensor",
        platform="curator_test",
        unique_id="disposable-2",
        object_id="disposable_event",
        config_entry=entry,
        original_name="Disposable Event Probe",
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device: dr.DeviceEntry
) -> bool:
    """Permit device removal.

    Home Assistant refuses `config/device_registry/remove_config_entry` unless
    the owning integration opts in here. Home Curator's `delete_device` walks
    every config entry on a device, so without this the multi-entry delete
    path is untestable.
    """
    return True


def _ensure_area(registry: ar.AreaRegistry, name: str) -> str:
    existing = registry.async_get_area_by_name(name)
    if existing is not None:
        return existing.id
    return registry.async_create(name).id


def _ensure_entity(
    registry: er.EntityRegistry,
    *,
    domain: str,
    platform: str,
    unique_id: str,
    object_id: str,
    config_entry: ConfigEntry,
    device_id: str | None = None,
    area_id: str | None = None,
    original_name: str | None = None,
    name: str | None = None,
    disabled_by: Any = None,
    hidden_by: Any = None,
) -> str:
    """Create a registry entry, then apply the fields that are update-only.

    `name` (the user's override), `area_id` and `hidden_by` are not accepted
    by `async_get_or_create` in every Home Assistant version, so they are
    applied through `async_update_entity` where support is stable.
    """
    entry = registry.async_get_or_create(
        domain,
        platform,
        unique_id,
        suggested_object_id=object_id,
        config_entry=config_entry,
        device_id=device_id,
        original_name=original_name,
        disabled_by=disabled_by,
    )
    updates: dict[str, Any] = {}
    if name is not None:
        updates["name"] = name
    if area_id is not None:
        updates["area_id"] = area_id
    if hidden_by is not None:
        updates["hidden_by"] = hidden_by
    if updates:
        registry.async_update_entity(entry.entity_id, **updates)
    return entry.entity_id
