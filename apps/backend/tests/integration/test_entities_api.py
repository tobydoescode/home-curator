def test_list_entities_default_excludes_disabled_and_hidden(client):
    r = client.get("/api/entities")
    assert r.status_code == 200
    body = r.json()
    ids = {e["entity_id"] for e in body["entities"]}
    # Baseline fixture has 6 entities; one disabled, one hidden.
    # Default must omit them.
    assert "switch.garage_door" not in ids
    assert "binary_sensor.kitchen_motion" not in ids
    assert body["total"] == 4
    assert body["page"] == 1
    assert body["page_size"] == 50


def test_list_entities_carries_display_and_device_names(client):
    r = client.get("/api/entities", params={"q": "light.lamp"})
    assert r.status_code == 200
    [row] = r.json()["entities"]
    assert row["entity_id"] == "light.lamp"
    # name is null, original_name is "Living Room Lamp"
    assert row["display_name"] == "Living Room Lamp"
    # Device join populates device_name (d1's display name).
    assert row["device_name"] == "living_room_lamp"
    # Our fixture puts light.lamp with area_id=null; device d1 is in "living".
    # The API returns the entity's own area_id; the cache hydrates area_name
    # from the device fallback.
    assert row["area_id"] is None


# --- Filter tests (Task 6) -------------------------------------------------

def test_filter_by_domain(client):
    r = client.get("/api/entities", params={"domain": ["light", "sensor"]})
    ids = {e["entity_id"] for e in r.json()["entities"]}
    # Defaults exclude switch.garage_door (disabled) and
    # binary_sensor.kitchen_motion (hidden).
    assert ids == {"light.lamp", "light.kitchen_ceiling", "sensor.temperature"}


def test_filter_by_room_case_insensitive(client):
    r = client.get("/api/entities", params={"room": ["kitchen"]})
    # Only light.kitchen_ceiling is kitchen + visible (motion is hidden).
    ids = {e["entity_id"] for e in r.json()["entities"]}
    assert ids == {"light.kitchen_ceiling"}


def test_filter_by_room_no_area_sentinel(client):
    r = client.get("/api/entities", params={"room": ["__none__"]})
    ids = {e["entity_id"] for e in r.json()["entities"]}
    # Entities with area_name=None that are visible:
    #   sensor.temperature (d2, no area),
    #   media_player.office (standalone, no area).
    # light.lamp's area_id is None but its effective area_name is "Living
    # Room" via the owning device, so it does NOT match the no-area sentinel.
    assert ids == {"sensor.temperature", "media_player.office"}


def test_filter_by_room_combined_with_area(client):
    # Combining a sentinel with a real area is OR.
    r = client.get("/api/entities", params={"room": ["__none__", "Kitchen"]})
    ids = {e["entity_id"] for e in r.json()["entities"]}
    # light.lamp resolves to Living Room, so it's excluded here.
    assert ids == {
        "sensor.temperature",
        "media_player.office",
        "light.kitchen_ceiling",
    }


def test_filter_by_integration(client):
    r = client.get("/api/entities", params={"integration": ["hue", "mqtt"]})
    ids = {e["entity_id"] for e in r.json()["entities"]}
    assert ids == {"light.lamp", "light.kitchen_ceiling"}


def test_filter_with_issues_only(client):
    r = client.get("/api/entities", params={"with_issues": "true"})
    # The conftest policies file is device-scoped; no entity-scope rules
    # compile issues yet. With no issues anywhere, with_issues=true returns 0.
    assert r.json()["total"] == 0


def test_show_disabled_toggle_surfaces_disabled(client):
    r = client.get("/api/entities", params={"show_disabled": "true"})
    ids = {e["entity_id"] for e in r.json()["entities"]}
    assert "switch.garage_door" in ids
    # Hidden still hidden.
    assert "binary_sensor.kitchen_motion" not in ids


def test_show_hidden_toggle_surfaces_hidden(client):
    r = client.get("/api/entities", params={"show_hidden": "true"})
    ids = {e["entity_id"] for e in r.json()["entities"]}
    assert "binary_sensor.kitchen_motion" in ids
    # Disabled still hidden.
    assert "switch.garage_door" not in ids


def test_show_both_surfaces_all(client):
    r = client.get(
        "/api/entities",
        params={"show_disabled": "true", "show_hidden": "true"},
    )
    assert r.json()["total"] == 6


# --- Search and regex tests (Task 7) ---------------------------------------

def test_search_matches_entity_id_and_display_name(client):
    # `lamp` matches light.lamp (entity_id) AND Living Room Lamp
    # (display_name). Result is the union.
    r = client.get("/api/entities", params={"q": "lamp"})
    ids = {e["entity_id"] for e in r.json()["entities"]}
    assert ids == {"light.lamp"}


def test_search_is_case_insensitive(client):
    r = client.get("/api/entities", params={"q": "KITCHEN"})
    ids = {e["entity_id"] for e in r.json()["entities"]}
    assert ids == {"light.kitchen_ceiling"}


def test_regex_mode_uses_re_search(client):
    r = client.get(
        "/api/entities",
        params={"q": r"^sensor\..*$", "regex": "true"},
    )
    ids = {e["entity_id"] for e in r.json()["entities"]}
    assert ids == {"sensor.temperature"}


def test_invalid_regex_returns_empty_not_500(client):
    r = client.get("/api/entities", params={"q": "[", "regex": "true"})
    assert r.status_code == 200
    assert r.json()["total"] == 0


# --- Pagination tests (Task 8) ---------------------------------------------

def test_pagination_page_size(client):
    r = client.get(
        "/api/entities",
        params={"page_size": 2, "page": 1, "sort_by": "entity_id"},
    )
    body = r.json()
    assert len(body["entities"]) == 2
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["total"] == 4

    r2 = client.get(
        "/api/entities",
        params={"page_size": 2, "page": 2, "sort_by": "entity_id"},
    )
    body2 = r2.json()
    assert len(body2["entities"]) == 2
    ids1 = {e["entity_id"] for e in body["entities"]}
    ids2 = {e["entity_id"] for e in body2["entities"]}
    assert ids1.isdisjoint(ids2)


def test_page_beyond_returns_empty(client):
    r = client.get("/api/entities", params={"page_size": 50, "page": 99})
    assert r.status_code == 200
    assert r.json()["entities"] == []


def test_page_size_bounds_reject_zero_and_over_500(client):
    r = client.get("/api/entities", params={"page_size": 0})
    assert r.status_code == 422
    r = client.get("/api/entities", params={"page_size": 501})
    assert r.status_code == 422


def test_page_bounds_reject_zero(client):
    r = client.get("/api/entities", params={"page": 0})
    assert r.status_code == 422


# --- Sort tests (Task 9) ---------------------------------------------------

def _ids(body):
    return [e["entity_id"] for e in body["entities"]]


def test_sort_entity_id_asc_desc(client):
    asc = _ids(client.get(
        "/api/entities", params={"sort_by": "entity_id", "sort_dir": "asc"},
    ).json())
    desc = _ids(client.get(
        "/api/entities", params={"sort_by": "entity_id", "sort_dir": "desc"},
    ).json())
    assert asc == sorted(asc)
    assert desc == list(reversed(asc))


def test_sort_name_uses_display_name(client):
    # light.lamp's display_name = Living Room Lamp (original_name fallback),
    # light.kitchen_ceiling's display_name = Kitchen Ceiling, etc.
    asc = _ids(client.get(
        "/api/entities", params={"sort_by": "name", "sort_dir": "asc"},
    ).json())
    # "Kitchen Ceiling" < "Living Room Lamp" < "Office Speaker" < "Temperature"
    assert asc == [
        "light.kitchen_ceiling",
        "light.lamp",
        "media_player.office",
        "sensor.temperature",
    ]


def test_sort_domain(client):
    asc = _ids(client.get(
        "/api/entities", params={"sort_by": "domain", "sort_dir": "asc"},
    ).json())
    # Domains: light, light, media_player, sensor
    assert [e.split(".")[0] for e in asc] == ["light", "light", "media_player", "sensor"]


def test_sort_room_missing_last_on_asc(client):
    asc = _ids(client.get(
        "/api/entities", params={"sort_by": "room", "sort_dir": "asc"},
    ).json())
    # light.lamp resolves to Living Room via device fallback, and
    # light.kitchen_ceiling is Kitchen. The two entities with area_name=None
    # (sensor.temperature, media_player.office) sort last on asc.
    assert asc[:2] == ["light.kitchen_ceiling", "light.lamp"]
    assert set(asc[2:]) == {"sensor.temperature", "media_player.office"}


def test_sort_device_missing_last_on_asc(client):
    asc = _ids(client.get(
        "/api/entities", params={"sort_by": "device", "sort_dir": "asc"},
    ).json())
    # light.lamp owns d1 (living_room_lamp), sensor.temperature owns d2
    # (BadCase). Rows without a device are sorted last on asc.
    assert asc[:2] == ["sensor.temperature", "light.lamp"]
    assert set(asc[2:]) == {"light.kitchen_ceiling", "media_player.office"}


def test_sort_integration(client):
    asc = _ids(client.get(
        "/api/entities", params={"sort_by": "integration", "sort_dir": "asc"},
    ).json())
    # platforms: aqara, cast, hue, mqtt
    assert asc == [
        "sensor.temperature",     # aqara
        "media_player.office",    # cast
        "light.lamp",             # hue
        "light.kitchen_ceiling",  # mqtt
    ]


def test_sort_severity_no_issues_stable(client):
    # With no entity-scope rules in the fixture, every row has severity 0.
    # Sort should still return a deterministic ordering.
    asc = _ids(client.get(
        "/api/entities", params={"sort_by": "severity", "sort_dir": "desc"},
    ).json())
    assert set(asc) == {
        "light.lamp", "light.kitchen_ceiling",
        "sensor.temperature", "media_player.office",
    }


def test_sort_created_asc(client):
    asc = _ids(client.get(
        "/api/entities", params={"sort_by": "created", "sort_dir": "asc"},
    ).json())
    # Fixture created_at values 2026-01-01…06. Visible set excludes the 4th
    # (disabled) and 5th (hidden). Order: lamp, kitchen_ceiling, temperature, office.
    assert asc == [
        "light.lamp",
        "light.kitchen_ceiling",
        "sensor.temperature",
        "media_player.office",
    ]


def test_sort_modified_desc(client):
    desc = _ids(client.get(
        "/api/entities", params={"sort_by": "modified", "sort_dir": "desc"},
    ).json())
    assert desc == [
        "media_player.office",
        "sensor.temperature",
        "light.kitchen_ceiling",
        "light.lamp",
    ]


def test_invalid_sort_by_returns_422(client):
    r = client.get("/api/entities", params={"sort_by": "nonsense"})
    assert r.status_code == 422


# --- Counts and universes tests (Task 10) ----------------------------------

def test_counts_reflect_filtered_result(client):
    r = client.get("/api/entities", params={"domain": ["light"]})
    body = r.json()
    # Two visible lights in the filtered result.
    assert body["domain_counts"]["light"] == 2
    # Other domains still listed with 0 — the frontend dims zero rows.
    assert body["domain_counts"].get("sensor", 0) == 0
    assert body["domain_counts"].get("media_player", 0) == 0


def test_filter_universes_stay_populated_under_filter(client):
    # Filtering by kitchen shouldn't collapse the domain dropdown.
    r = client.get("/api/entities", params={"room": ["Kitchen"]})
    body = r.json()
    # Domains universe enumerates all visible entities regardless of the
    # current room selection, so the dropdown still shows every option.
    assert set(body["all_domains"]) >= {"light", "sensor", "media_player"}
    assert {"hue", "mqtt", "aqara", "cast"}.issubset(set(body["all_integrations"]))
    # Areas universe is the full registry, not filtered.
    area_names = {a["name"] for a in body["all_areas"]}
    assert area_names == {"Living Room", "Kitchen", "Garage"}


def test_area_counts_dim_zero_for_rooms_with_no_visible_entities(client):
    r = client.get("/api/entities")
    body = r.json()
    # light.lamp's effective area_name resolves to "Living Room" via the
    # owning device, so Living Room has 1 visible entity — not zero.
    assert body["area_counts"]["Living Room"] == 1
    # Kitchen has light.kitchen_ceiling visible.
    assert body["area_counts"]["Kitchen"] == 1
    # Garage has only the disabled switch; visible count = 0.
    assert body["area_counts"]["Garage"] == 0


def test_all_issue_types_lists_only_entity_scope_rule_types(client):
    # Fixture has no entity-scope rules, so the list is empty.
    r = client.get("/api/entities")
    assert r.json()["all_issue_types"] == []
