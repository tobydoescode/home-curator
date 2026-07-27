"""Pin down the wire contract Home Curator reads from Home Assistant.

`ha_client/websocket.py` is written against commands that are absent from
HA's published API reference, so several of its assumptions are inferences
from observed behaviour. These tests turn those inferences into assertions
against a real instance.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from websockets.asyncio.client import connect

pytestmark = pytest.mark.realha


async def _raw_command(ws_url: str, token: str, payload: dict[str, Any]) -> Any:
    """Run one websocket command and return HA's untouched `result`.

    Deliberately bypasses `WebSocketHAClient` so the assertions describe what
    Home Assistant actually sends, not what our parsing layer makes of it.
    """
    async with connect(ws_url, max_size=None) as ws:
        first = json.loads(await ws.recv())
        assert first["type"] == "auth_required"
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        assert json.loads(await ws.recv())["type"] == "auth_ok"

        await ws.send(json.dumps({"id": 1, **payload}))
        while True:
            message = json.loads(await ws.recv())
            if message.get("id") == 1 and message.get("type") == "result":
                assert message["success"], message
                return message["result"]


# --- raw wire shape ------------------------------------------------------


async def test_device_registry_timestamps_are_unix_floats(ha_ws_url, ha_token):
    """`_iso_or_none` assumes created_at / modified_at arrive as numbers.

    That assumption is load-bearing — if HA ever switched to ISO strings the
    helper would pass them through unchanged and the API would start emitting
    a different format without anything failing.
    """
    devices = await _raw_command(
        ha_ws_url, ha_token, {"type": "config/device_registry/list"}
    )
    assert devices

    sampled = [d for d in devices if "created_at" in d]
    assert sampled, "no device carried a created_at field"
    for device in sampled:
        assert isinstance(device["created_at"], (int, float)), (
            f"created_at was {type(device['created_at']).__name__}: "
            f"{device['created_at']!r}"
        )
        assert isinstance(device["modified_at"], (int, float))


async def test_device_registry_exposes_fields_the_client_reads(ha_ws_url, ha_token):
    """Every key `get_devices` indexes into must actually be present."""
    devices = await _raw_command(
        ha_ws_url, ha_token, {"type": "config/device_registry/list"}
    )
    device = next(d for d in devices if d.get("name") == "living_room_lamp")

    # `get_devices` subscripts these directly, so a rename upstream would be
    # a KeyError at runtime rather than a missing field.
    assert isinstance(device["id"], str)
    assert isinstance(device["config_entries"], list)
    assert device["config_entries"]
    assert isinstance(device["identifiers"], list)
    for key in ("name_by_user", "manufacturer", "model", "area_id", "disabled_by"):
        assert key in device, f"device registry no longer sends {key!r}"


async def test_entity_registry_always_sends_device_id(ha_ws_url, ha_token):
    """`get_devices` builds its entity index with `e["device_id"]`.

    That is an unguarded subscript, so a standalone entity omitting the key
    would take down every device listing.
    """
    entities = await _raw_command(
        ha_ws_url, ha_token, {"type": "config/entity_registry/list"}
    )
    assert entities
    for entity in entities:
        assert "device_id" in entity, f"{entity['entity_id']} omitted device_id"


async def test_config_entries_expose_domain(ha_ws_url, ha_token):
    """A device's `integration` is resolved through `config_entries/get`."""
    entries = await _raw_command(ha_ws_url, ha_token, {"type": "config_entries/get"})
    ours = [e for e in entries if e.get("domain") == "curator_test"]
    assert len(ours) == 2, "expected the fixture's two config entries"
    for entry in ours:
        assert isinstance(entry["entry_id"], str)


# --- parsed reads through the real client --------------------------------


async def test_get_devices_parses_the_fixture(ha_client):
    devices = {d.name: d for d in await ha_client.get_devices()}

    lamp = devices["living_room_lamp"]
    assert lamp.manufacturer == "Signify"
    assert lamp.model == "m"
    assert lamp.area_id is not None
    # Derived from the owning config entry's domain, which for a fixture
    # integration is always `curator_test`.
    assert lamp.integration == "curator_test"
    assert ["curator_test", "d1"] in lamp.identifiers
    assert lamp.config_entries
    assert {e.id for e in lamp.entities} == {"light.lamp"}
    # Proves `_iso_or_none` converted the float rather than dropping it.
    assert lamp.created_at is not None
    assert lamp.created_at.startswith("20")

    assert "BadCase" in devices
    assert devices["BadCase"].area_id is None


async def test_get_areas_parses_the_fixture(ha_client):
    areas = {a.name for a in await ha_client.get_areas()}
    assert {"Living Room", "Kitchen", "Garage"} <= areas


async def test_get_entities_parses_the_fixture(ha_client):
    entities = {e.entity_id: e for e in await ha_client.get_entities()}

    lamp = entities["light.lamp"]
    assert lamp.platform == "hue"
    assert lamp.unique_id == "hue-lamp-1"
    assert lamp.original_name == "Living Room Lamp"
    assert lamp.name is None
    assert lamp.device_id is not None
    # The entity has no area of its own; the effective area comes from its
    # device, and resolving that is the cache's job, not the client's.
    assert lamp.area_id is None

    ceiling = entities["light.kitchen_ceiling"]
    assert ceiling.name == "Kitchen Ceiling"
    assert ceiling.original_name == "Ceiling Light"
    assert ceiling.area_id is not None
    assert ceiling.platform == "mqtt"

    assert entities["switch.garage_door"].disabled_by == "user"
    assert entities["binary_sensor.kitchen_motion"].hidden_by == "user"

    office = entities["media_player.office"]
    assert office.device_id is None
    assert office.name == "Office Speaker"


async def test_disabled_and_hidden_entities_are_listed(ha_client):
    """Home Curator filters these itself, so the registry must return them."""
    entity_ids = {e.entity_id for e in await ha_client.get_entities()}
    assert "switch.garage_door" in entity_ids
    assert "binary_sensor.kitchen_motion" in entity_ids
