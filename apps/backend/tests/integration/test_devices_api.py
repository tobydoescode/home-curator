def test_lists_all_devices(client):
    r = client.get("/api/devices")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    ids = sorted(d["id"] for d in data["devices"])
    assert ids == ["d1", "d2"]


def test_filters_by_room(client):
    r = client.get("/api/devices", params={"room": "Living Room"})
    data = r.json()
    assert [d["id"] for d in data["devices"]] == ["d1"]


def test_filters_by_issue_type(client):
    r = client.get("/api/devices", params={"issue_type": "missing_area"})
    data = r.json()
    assert [d["id"] for d in data["devices"]] == ["d2"]


def test_filters_with_issues_only(client):
    r = client.get("/api/devices", params={"with_issues": "true"})
    data = r.json()
    ids = sorted(d["id"] for d in data["devices"])
    assert ids == ["d2"]  # d1 is snake_case + has room; d2 fails both


def test_search_substring(client):
    r = client.get("/api/devices", params={"q": "bad"})
    data = r.json()
    assert [d["id"] for d in data["devices"]] == ["d2"]


def test_search_regex(client):
    r = client.get("/api/devices", params={"q": "^living_", "regex": "true"})
    data = r.json()
    assert [d["id"] for d in data["devices"]] == ["d1"]


def test_pagination(client):
    r = client.get("/api/devices", params={"page": 1, "page_size": 1})
    data = r.json()
    assert data["total"] == 2
    assert data["page"] == 1
    assert len(data["devices"]) == 1


def test_invalid_regex_returns_empty_list(client):
    r = client.get("/api/devices", params={"q": "][invalid", "regex": "true"})
    assert r.status_code == 200
    assert r.json()["devices"] == []


def test_page_size_too_large_returns_422(client):
    r = client.get("/api/devices", params={"page_size": 501})
    assert r.status_code == 422


def test_issue_summary(client):
    r = client.get("/api/devices")
    data = r.json()
    d2 = [d for d in data["devices"] if d["id"] == "d2"][0]
    # d2 has BadCase name + missing room → 2 issues
    assert d2["issue_count"] == 2
    assert d2["highest_severity"] == "warning"
    assert {i["policy_id"] for i in d2["issues"]} == {"naming-convention", "missing-room"}
    assert data["issue_counts_by_type"]["missing_area"] == 1
    assert data["issue_counts_by_type"]["naming_convention"] == 1
