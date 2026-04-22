def test_list_policies(client):
    r = client.get("/api/policies")
    assert r.status_code == 200
    body = r.json()
    assert body["error"] is None
    ids = sorted(p["id"] for p in body["policies"])
    assert ids == ["missing-room", "naming-convention"]


def test_update_policies_round_trips(client):
    import time

    new_body = {
        "version": 1,
        "policies": [
            {"id": "missing-room", "type": "missing_area", "enabled": False, "severity": "info"},
        ],
    }
    r = client.put("/api/policies", json=new_body)
    assert r.status_code == 200
    assert r.json() == {"ok": True, "error": None}

    deadline = time.time() + 3
    while time.time() < deadline:
        got = client.get("/api/policies").json()
        if any(p["id"] == "missing-room" and not p["enabled"] for p in got["policies"]):
            return
        time.sleep(0.1)
    raise AssertionError("update not reflected")


def test_update_policies_rejects_invalid(client):
    r = client.put(
        "/api/policies",
        json={"version": 1, "policies": [{"type": "unknown_type", "id": "x", "severity": "info"}]},
    )
    assert r.status_code == 422


def test_policy_includes_compile_errors(client):
    r = client.get("/api/policies")
    body = r.json()
    for p in body["policies"]:
        assert "compile_error" in p


def test_get_policies_file_returns_full_shape(client):
    r = client.get("/api/policies/file")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == 1
    nc = next(p for p in body["policies"] if p["type"] == "naming_convention")
    assert "global" in nc
    assert "starts_with_room" in nc
    assert "rooms" in nc
