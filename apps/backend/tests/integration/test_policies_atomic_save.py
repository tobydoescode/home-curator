"""Saving policies through the API must still trigger a reload.

`PUT /api/policies` writes the file but does not recompile the engine — it
relies on the file watcher noticing. Since C-7 that write is atomic, so the
file is *replaced* rather than modified in place, and the watcher filters
events down to the policies file. If either half were wrong, saving from the
UI would appear to succeed and silently never take effect.
"""

import time

from ruamel.yaml import YAML


def _policies(client) -> dict[str, bool]:
    body = client.get("/api/policies").json()
    return {p["id"]: p["enabled"] for p in body["policies"]}


def _wait_for(client, predicate, timeout: float = 5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        current = _policies(client)
        if predicate(current):
            return current
        time.sleep(0.1)
    raise AssertionError(f"reload did not happen; last state: {_policies(client)}")


def test_saving_through_the_api_reaches_the_engine(client):
    """The atomic rename has to be something the watcher still reacts to."""
    assert _policies(client)["missing-room"] is True

    response = client.put(
        "/api/policies",
        json={
            "version": 1,
            "policies": [
                {
                    "id": "missing-room",
                    "type": "missing_area",
                    "enabled": False,
                    "severity": "warning",
                }
            ],
        },
    )
    assert response.status_code == 200, response.text

    _wait_for(client, lambda p: p.get("missing-room") is False)


def test_save_leaves_no_temporary_file_behind(client, tmp_path):
    config_dir = tmp_path / "config"

    client.put(
        "/api/policies",
        json={"version": 1, "policies": []},
    )

    assert sorted(p.name for p in config_dir.iterdir()) == ["policies.yaml"]


def test_saved_file_is_complete_and_parses(client, tmp_path):
    """A half-written file was the failure mode this fix exists to prevent."""
    client.put(
        "/api/policies",
        json={
            "version": 1,
            "policies": [
                {
                    "id": "missing-room",
                    "type": "missing_area",
                    "enabled": True,
                    "severity": "error",
                }
            ],
        },
    )

    written = (tmp_path / "config" / "policies.yaml").read_text()
    parsed = YAML(typ="safe").load(written)
    assert parsed["version"] == 1
    assert parsed["policies"][0]["severity"] == "error"
