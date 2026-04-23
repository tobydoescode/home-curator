def test_patch_entity_name_only(client, fake_ha):
    r = client.patch(
        "/api/actions/entity/light.kitchen_ceiling",
        json={"name": "Main Ceiling"},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert fake_ha.update_entity_calls[-1] == (
        "light.kitchen_ceiling",
        {"name": "Main Ceiling"},
    )


def test_patch_entity_rename_slug(client, fake_ha):
    r = client.patch(
        "/api/actions/entity/light.kitchen_ceiling",
        json={"new_entity_id": "light.study_lamp"},
    )
    assert r.status_code == 200
    assert fake_ha.update_entity_calls[-1] == (
        "light.kitchen_ceiling",
        {"new_entity_id": "light.study_lamp"},
    )


def test_patch_entity_batches_fields_into_one_call(client, fake_ha):
    before = len(fake_ha.update_entity_calls)
    r = client.patch(
        "/api/actions/entity/light.kitchen_ceiling",
        json={"name": "Main Ceiling", "area_id": "living", "icon": None},
    )
    assert r.status_code == 200
    assert len(fake_ha.update_entity_calls) == before + 1
    assert fake_ha.update_entity_calls[-1] == (
        "light.kitchen_ceiling",
        {"name": "Main Ceiling", "area_id": "living", "icon": None},
    )


def test_patch_entity_empty_body_rejected(client, fake_ha):
    before = len(fake_ha.update_entity_calls)
    r = client.patch("/api/actions/entity/light.kitchen_ceiling", json={})
    assert r.status_code == 400
    assert len(fake_ha.update_entity_calls) == before


def test_patch_entity_extra_field_forbidden(client):
    r = client.patch(
        "/api/actions/entity/light.kitchen_ceiling",
        json={"name": "x", "bogus": 1},
    )
    assert r.status_code == 422


def test_patch_entity_ha_error_surfaces_as_502(client, fake_ha):
    async def boom(eid, changes):
        del eid, changes
        raise RuntimeError("ha refused")

    fake_ha.update_entity = boom  # type: ignore[method-assign]
    r = client.patch(
        "/api/actions/entity/light.kitchen_ceiling",
        json={"name": "x"},
    )
    assert r.status_code == 502
    assert "ha refused" in r.json()["detail"]


# --- assign-room-entities (Phase 5) ----------------------------------------

def test_assign_room_entities_bulk(client, fake_ha):
    r = client.post(
        "/api/actions/assign-room-entities",
        json={
            "entity_ids": ["light.kitchen_ceiling", "sensor.temperature"],
            "area_id": "living",
        },
    )
    assert r.status_code == 200
    rows = r.json()["results"]
    assert rows == [
        {"entity_id": "light.kitchen_ceiling", "ok": True},
        {"entity_id": "sensor.temperature", "ok": True},
    ]
    assert fake_ha.update_entity_calls[-2:] == [
        ("light.kitchen_ceiling", {"area_id": "living"}),
        ("sensor.temperature", {"area_id": "living"}),
    ]


def test_assign_room_entities_partial_failure(client, fake_ha):
    original = fake_ha.update_entity

    async def flaky(eid, changes):
        if eid == "sensor.temperature":
            raise RuntimeError("integration refused")
        await original(eid, changes)

    fake_ha.update_entity = flaky  # type: ignore[method-assign]

    r = client.post(
        "/api/actions/assign-room-entities",
        json={
            "entity_ids": ["light.kitchen_ceiling", "sensor.temperature"],
            "area_id": "living",
        },
    )
    assert r.status_code == 200
    rows = {row["entity_id"]: row for row in r.json()["results"]}
    assert rows["light.kitchen_ceiling"] == {
        "entity_id": "light.kitchen_ceiling", "ok": True,
    }
    assert rows["sensor.temperature"]["ok"] is False
    assert "integration refused" in rows["sensor.temperature"]["error"]


# --- rename-pattern-entities (Phase 6) -------------------------------------

def test_rename_pattern_dry_run_both_regexes(client, fake_ha):
    before = len(fake_ha.update_entity_calls)
    r = client.post(
        "/api/actions/rename-pattern-entities",
        json={
            "entity_ids": ["light.kitchen_ceiling"],
            "id_pattern": r"^light\.kitchen_(.+)$",
            "id_replacement": r"light.main_\1",
            "name_pattern": r"^Kitchen\s+(.+)$",
            "name_replacement": r"Main \1",
            "dry_run": True,
        },
    )
    assert r.status_code == 200
    [row] = r.json()["results"]
    assert row == {
        "entity_id": "light.kitchen_ceiling",
        "id_changed": True,
        "new_entity_id": "light.main_ceiling",
        "name_changed": True,
        "new_name": "Main Ceiling",
        "ok": True,
        "dry_run": True,
        "error": None,
    }
    # No HA writes on dry_run.
    assert len(fake_ha.update_entity_calls) == before


def test_rename_pattern_apply_sends_changed_fields_only(client, fake_ha):
    # Apply only the id rename; leave name untouched.
    before = len(fake_ha.update_entity_calls)
    r = client.post(
        "/api/actions/rename-pattern-entities",
        json={
            "entity_ids": ["light.kitchen_ceiling"],
            "id_pattern": r"^light\.kitchen_(.+)$",
            "id_replacement": r"light.main_\1",
            "dry_run": False,
        },
    )
    assert r.status_code == 200
    [row] = r.json()["results"]
    assert row["ok"] is True
    assert row["id_changed"] is True
    assert row["name_changed"] is False
    assert len(fake_ha.update_entity_calls) == before + 1
    assert fake_ha.update_entity_calls[-1] == (
        "light.kitchen_ceiling",
        {"new_entity_id": "light.main_ceiling"},
    )


def test_rename_pattern_name_only_apply(client, fake_ha):
    r = client.post(
        "/api/actions/rename-pattern-entities",
        json={
            "entity_ids": ["light.kitchen_ceiling"],
            "name_pattern": r"^Kitchen\s+(.+)$",
            "name_replacement": r"Main \1",
            "dry_run": False,
        },
    )
    assert r.status_code == 200
    assert fake_ha.update_entity_calls[-1] == (
        "light.kitchen_ceiling",
        {"name": "Main Ceiling"},
    )


def test_rename_pattern_invalid_id_pattern_top_level_error(client):
    r = client.post(
        "/api/actions/rename-pattern-entities",
        json={
            "entity_ids": ["light.kitchen_ceiling"],
            "id_pattern": "[",
            "id_replacement": "x",
            "dry_run": True,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["results"] == []
    assert "invalid id_pattern" in body["error"]


def test_rename_pattern_invalid_name_pattern_top_level_error(client):
    r = client.post(
        "/api/actions/rename-pattern-entities",
        json={
            "entity_ids": ["light.kitchen_ceiling"],
            "name_pattern": "[",
            "name_replacement": "x",
            "dry_run": True,
        },
    )
    assert r.status_code == 200
    assert "invalid name_pattern" in r.json()["error"]


def test_rename_pattern_requires_at_least_one_side(client):
    r = client.post(
        "/api/actions/rename-pattern-entities",
        json={"entity_ids": ["light.kitchen_ceiling"], "dry_run": True},
    )
    assert r.status_code == 200
    assert "at least one" in r.json()["error"].lower()


def test_rename_pattern_collision_surfaces_per_entity(client, fake_ha):
    # Simulate HA refusing the new slug (already exists).
    original = fake_ha.update_entity

    async def colliding(eid, changes):
        if "new_entity_id" in changes:
            raise RuntimeError("entity_id already exists")
        await original(eid, changes)

    fake_ha.update_entity = colliding  # type: ignore[method-assign]

    r = client.post(
        "/api/actions/rename-pattern-entities",
        json={
            "entity_ids": ["light.kitchen_ceiling"],
            "id_pattern": r"^light\.kitchen_(.+)$",
            "id_replacement": r"light.main_\1",
            "dry_run": False,
        },
    )
    assert r.status_code == 200
    [row] = r.json()["results"]
    assert row["ok"] is False
    assert "already exists" in row["error"]


def test_rename_pattern_skips_non_matching(client, fake_ha):
    before = len(fake_ha.update_entity_calls)
    r = client.post(
        "/api/actions/rename-pattern-entities",
        json={
            "entity_ids": ["light.kitchen_ceiling", "sensor.temperature"],
            "id_pattern": r"^light\.kitchen_(.+)$",
            "id_replacement": r"light.main_\1",
            "dry_run": False,
        },
    )
    assert r.status_code == 200
    rows = {row["entity_id"]: row for row in r.json()["results"]}
    # sensor.temperature doesn't match — reported ok=true, id_changed=false,
    # no HA write for that one.
    assert rows["sensor.temperature"]["id_changed"] is False
    assert rows["sensor.temperature"]["ok"] is True
    writes_after = fake_ha.update_entity_calls[before:]
    assert len(writes_after) == 1
    assert writes_after[0][0] == "light.kitchen_ceiling"


# --- entity-state (Phase 7) ------------------------------------------------

def test_entity_state_disable(client, fake_ha):
    r = client.post(
        "/api/actions/entity-state",
        json={
            "entity_ids": ["light.kitchen_ceiling"],
            "field": "disabled_by",
            "value": "user",
        },
    )
    assert r.status_code == 200
    assert r.json()["results"] == [{"entity_id": "light.kitchen_ceiling", "ok": True}]
    assert fake_ha.update_entity_calls[-1] == (
        "light.kitchen_ceiling",
        {"disabled_by": "user"},
    )


def test_entity_state_enable(client, fake_ha):
    r = client.post(
        "/api/actions/entity-state",
        json={
            "entity_ids": ["switch.garage_door"],
            "field": "disabled_by",
            "value": None,
        },
    )
    assert r.status_code == 200
    assert fake_ha.update_entity_calls[-1] == (
        "switch.garage_door",
        {"disabled_by": None},
    )


def test_entity_state_hide(client, fake_ha):
    r = client.post(
        "/api/actions/entity-state",
        json={
            "entity_ids": ["light.kitchen_ceiling"],
            "field": "hidden_by",
            "value": "user",
        },
    )
    assert r.status_code == 200
    assert fake_ha.update_entity_calls[-1] == (
        "light.kitchen_ceiling",
        {"hidden_by": "user"},
    )


def test_entity_state_show(client, fake_ha):
    r = client.post(
        "/api/actions/entity-state",
        json={
            "entity_ids": ["binary_sensor.kitchen_motion"],
            "field": "hidden_by",
            "value": None,
        },
    )
    assert r.status_code == 200
    assert fake_ha.update_entity_calls[-1] == (
        "binary_sensor.kitchen_motion",
        {"hidden_by": None},
    )


def test_entity_state_ha_refusal_is_per_row(client, fake_ha):
    original = fake_ha.update_entity

    async def flaky(eid, changes):
        if eid == "switch.garage_door":
            raise RuntimeError("integration disabled this entity")
        await original(eid, changes)

    fake_ha.update_entity = flaky  # type: ignore[method-assign]
    r = client.post(
        "/api/actions/entity-state",
        json={
            "entity_ids": ["light.kitchen_ceiling", "switch.garage_door"],
            "field": "disabled_by",
            "value": None,
        },
    )
    assert r.status_code == 200
    rows = {row["entity_id"]: row for row in r.json()["results"]}
    assert rows["light.kitchen_ceiling"]["ok"] is True
    assert rows["switch.garage_door"]["ok"] is False
    assert "integration disabled" in rows["switch.garage_door"]["error"]


def test_entity_state_invalid_field_rejected(client):
    r = client.post(
        "/api/actions/entity-state",
        json={
            "entity_ids": ["light.kitchen_ceiling"],
            "field": "name",
            "value": "x",
        },
    )
    assert r.status_code == 422


def test_entity_state_invalid_value_rejected(client):
    r = client.post(
        "/api/actions/entity-state",
        json={
            "entity_ids": ["light.kitchen_ceiling"],
            "field": "disabled_by",
            "value": "integration",
        },
    )
    assert r.status_code == 422


def test_entity_state_empty_body_rejected(client, fake_ha):
    before = len(fake_ha.update_entity_calls)
    r = client.post(
        "/api/actions/entity-state",
        json={"entity_ids": [], "field": "disabled_by", "value": "user"},
    )
    assert r.status_code == 400
    assert len(fake_ha.update_entity_calls) == before


# --- delete-entity (Phase 8) -----------------------------------------------

def test_delete_entity_single_ok(client, fake_ha):
    r = client.post(
        "/api/actions/delete-entity",
        json={"entity_ids": ["light.kitchen_ceiling"]},
    )
    assert r.status_code == 200
    assert r.json() == {
        "results": [{"entity_id": "light.kitchen_ceiling", "ok": True}],
    }
    assert fake_ha.delete_entity_calls == ["light.kitchen_ceiling"]


def test_delete_entity_bulk(client, fake_ha):
    r = client.post(
        "/api/actions/delete-entity",
        json={"entity_ids": ["light.kitchen_ceiling", "sensor.temperature"]},
    )
    assert r.status_code == 200
    rows = {row["entity_id"]: row for row in r.json()["results"]}
    assert rows["light.kitchen_ceiling"]["ok"] is True
    assert rows["sensor.temperature"]["ok"] is True
    assert set(fake_ha.delete_entity_calls) == {
        "light.kitchen_ceiling", "sensor.temperature",
    }


def test_delete_entity_partial_failure(client, fake_ha):
    original = fake_ha.delete_entity

    async def flaky(eid):
        if eid == "sensor.temperature":
            raise RuntimeError("integration refused removal")
        await original(eid)

    fake_ha.delete_entity = flaky  # type: ignore[method-assign]
    r = client.post(
        "/api/actions/delete-entity",
        json={"entity_ids": ["light.kitchen_ceiling", "sensor.temperature"]},
    )
    assert r.status_code == 200
    rows = {row["entity_id"]: row for row in r.json()["results"]}
    assert rows["light.kitchen_ceiling"]["ok"] is True
    assert rows["sensor.temperature"]["ok"] is False
    assert "integration refused" in rows["sensor.temperature"]["error"]


def test_delete_entity_empty_rejected(client, fake_ha):
    before = len(fake_ha.delete_entity_calls)
    r = client.post("/api/actions/delete-entity", json={"entity_ids": []})
    assert r.status_code == 400
    assert len(fake_ha.delete_entity_calls) == before


def test_delete_entity_unknown_marks_not_found(client, fake_ha):
    r = client.post(
        "/api/actions/delete-entity",
        json={"entity_ids": ["ghost.missing"]},
    )
    assert r.status_code == 200
    assert r.json() == {
        "results": [
            {"entity_id": "ghost.missing", "ok": False, "error": "entity not found"},
        ]
    }
    assert "ghost.missing" not in fake_ha.delete_entity_calls
