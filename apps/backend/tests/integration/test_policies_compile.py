def test_compile_valid_custom(client):
    body = {
        "id": "t", "type": "custom", "scope": "devices", "severity": "info",
        "when": "true", "assert": "device.area_id != null", "message": "m",
    }
    r = client.post("/api/policies/compile", json=body)
    assert r.status_code == 200
    assert r.json() == {"ok": True, "error": None, "position": None}


def test_compile_invalid_custom(client):
    body = {
        "id": "t", "type": "custom", "scope": "devices", "severity": "info",
        "when": "true", "assert": "device.area_id &&&", "message": "m",
    }
    r = client.post("/api/policies/compile", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is False
    assert data["error"]


def test_compile_rejects_unknown_type(client):
    r = client.post("/api/policies/compile", json={
        "id": "t", "type": "nope", "severity": "info",
    })
    assert r.status_code == 422
