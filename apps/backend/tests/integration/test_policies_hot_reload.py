import time


def test_policy_edit_triggers_reload(client, tmp_path):
    # Sanity: 2 policies currently
    r = client.get("/api/policies")
    assert len(r.json()["policies"]) == 2

    # Edit the file: disable missing-room
    policies_path = tmp_path / "config" / "policies.yaml"
    text = policies_path.read_text()
    policies_path.write_text(text.replace(
        "  - id: missing-room\n    type: missing_area\n    enabled: true",
        "  - id: missing-room\n    type: missing_area\n    enabled: false",
    ))
    # Poll up to 3s for reload
    deadline = time.time() + 3
    while time.time() < deadline:
        r = client.get("/api/policies")
        disabled = [p for p in r.json()["policies"] if p["id"] == "missing-room" and not p["enabled"]]
        if disabled:
            return
        time.sleep(0.2)
    raise AssertionError("policy reload did not happen")
