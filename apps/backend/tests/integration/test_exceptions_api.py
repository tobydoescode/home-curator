def test_acknowledge_and_clear(client):
    # d2 has 2 issues initially
    r = client.get("/api/devices", params={"with_issues": "true"})
    assert r.json()["total"] == 1

    # Acknowledge missing-room for d2
    r = client.post(
        "/api/exceptions",
        json={"device_id": "d2", "policy_id": "missing-room", "note": "known"},
    )
    assert r.status_code == 201

    # Now d2 only has the naming issue
    r = client.get("/api/devices", params={"q": "BadCase"})
    d2 = r.json()["devices"][0]
    assert d2["issue_count"] == 1
    assert d2["issues"][0]["policy_id"] == "naming-convention"

    # Clear exception
    r = client.delete("/api/exceptions/d2/missing-room")
    assert r.status_code == 204

    r = client.get("/api/devices", params={"q": "BadCase"})
    assert r.json()["devices"][0]["issue_count"] == 2


def test_list_exceptions_for_device(client):
    client.post(
        "/api/exceptions",
        json={"device_id": "d2", "policy_id": "missing-room"},
    )
    r = client.get("/api/exceptions", params={"device_id": "d2"})
    assert r.status_code == 200
    assert [e["policy_id"] for e in r.json()] == ["missing-room"]


def test_acknowledged_by_stored(client):
    client.post(
        "/api/exceptions",
        json={
            "device_id": "d2",
            "policy_id": "missing-room",
            "acknowledged_by": "alice",
            "note": "verified",
        },
    )
    r = client.get("/api/exceptions", params={"device_id": "d2"})
    body = r.json()
    assert body[0]["acknowledged_by"] == "alice"
    assert body[0]["note"] == "verified"


def test_list_paginated_shape(client):
    client.post("/api/exceptions", json={"device_id": "d1", "policy_id": "missing-room"})
    client.post("/api/exceptions", json={"device_id": "d2", "policy_id": "missing-room"})
    r = client.get("/api/exceptions/list", params={"page": 1, "page_size": 10})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 2
    assert body["page"] == 1
    assert body["page_size"] == 10
    assert "exceptions" in body
    row = body["exceptions"][0]
    for key in ("id", "device_id", "device_name", "policy_id", "policy_name", "acknowledged_at"):
        assert key in row


def test_list_filters_by_policy_id(client):
    client.post("/api/exceptions", json={"device_id": "d1", "policy_id": "missing-room"})
    client.post("/api/exceptions", json={"device_id": "d1", "policy_id": "some-other"})
    r = client.get("/api/exceptions/list", params={"policy_id": "missing-room"})
    assert r.status_code == 200
    rows = r.json()["exceptions"]
    assert all(row["policy_id"] == "missing-room" for row in rows)
