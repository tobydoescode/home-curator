def test_put_policies_cascades_orphan_exceptions(client):
    # 1. Acknowledge an exception against an existing policy.
    listing = client.get("/api/policies").json()
    any_policy_id = listing["policies"][0]["id"]
    ack = client.post("/api/exceptions", json={
        "device_id": "fake-1", "policy_id": any_policy_id,
    })
    assert ack.status_code in (200, 201)

    # 2. PUT a policies file that omits that policy entirely.
    new_file = {
        "version": 1,
        "policies": [{
            "id": "only-missing-area", "type": "missing_area",
            "enabled": True, "severity": "warning",
        }],
    }
    put = client.put("/api/policies", json=new_file)
    assert put.status_code == 200

    # 3. The exception is gone.
    remaining = client.get("/api/exceptions", params={"device_id": "fake-1"}).json()
    rows = remaining if isinstance(remaining, list) else remaining.get("exceptions", [])
    assert all(r["policy_id"] != any_policy_id for r in rows)
