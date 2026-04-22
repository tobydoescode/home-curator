def test_list_policies(client):
    r = client.get("/api/policies")
    assert r.status_code == 200
    body = r.json()
    assert body["error"] is None
    ids = sorted(p["id"] for p in body["policies"])
    assert ids == ["missing-room", "naming-convention"]


def test_policy_includes_compile_errors(client):
    r = client.get("/api/policies")
    body = r.json()
    for p in body["policies"]:
        assert "compile_error" in p
