def test_list_areas(client):
    r = client.get("/api/areas")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    if body:
        assert "id" in body[0] and "name" in body[0]
