"""Area filtering on `GET /api/exceptions/list`.

The `area_id` filter used to be applied in Python *after* the repository had
already paginated, so it only ever saw one page: matches beyond the first
page were unreachable and `total` reported a per-page count. It also tested
an entity's own `area_id`, which ignores the area an entity inherits from its
device — the opposite of how `/api/entities` defines "in an area".

Nothing covered this, and the parameter is not yet wired up in the UI, so it
was invisible from both directions.
"""

import pytest
from fastapi.testclient import TestClient

LIVING_ROOM = "living"
KITCHEN = "kitchen"


def _ack_device(client: TestClient, device_id: str, policy_id: str) -> None:
    response = client.post(
        "/api/exceptions", json={"device_id": device_id, "policy_id": policy_id}
    )
    assert response.status_code == 201, response.text


def _ack_entity(client: TestClient, entity_id: str, policy_id: str) -> None:
    response = client.post(
        "/api/exceptions", json={"entity_id": entity_id, "policy_id": policy_id}
    )
    assert response.status_code == 201, response.text


@pytest.fixture
def client_with_many_exceptions(client: TestClient) -> TestClient:
    """60 exceptions on a Living Room device, 10 on a device with no area.

    Deliberately more than one page, which is what the original bug needed to
    show itself.
    """
    for i in range(60):
        _ack_device(client, "d1", f"policy-{i:03d}")
    for i in range(10):
        _ack_device(client, "d2", f"noarea-{i:03d}")
    return client


def test_area_filter_counts_the_whole_match_set(client_with_many_exceptions):
    """`total` must describe every match, not just those on this page."""
    body = client_with_many_exceptions.get(
        "/api/exceptions/list",
        params={"area_id": LIVING_ROOM, "page_size": 50},
    ).json()

    assert body["total"] == 60
    assert len(body["exceptions"]) == 50


def test_area_filter_reaches_later_pages(client_with_many_exceptions):
    """Previously page 2 was filtered from page 2's *unfiltered* rows."""
    page_2 = client_with_many_exceptions.get(
        "/api/exceptions/list",
        params={"area_id": LIVING_ROOM, "page": 2, "page_size": 50},
    ).json()

    assert page_2["total"] == 60
    assert len(page_2["exceptions"]) == 10
    assert all(r["device_id"] == "d1" for r in page_2["exceptions"])


def test_area_filter_pages_do_not_overlap(client_with_many_exceptions):
    first = client_with_many_exceptions.get(
        "/api/exceptions/list",
        params={"area_id": LIVING_ROOM, "page": 1, "page_size": 50},
    ).json()
    second = client_with_many_exceptions.get(
        "/api/exceptions/list",
        params={"area_id": LIVING_ROOM, "page": 2, "page_size": 50},
    ).json()

    ids = [r["id"] for r in first["exceptions"]] + [
        r["id"] for r in second["exceptions"]
    ]
    assert len(ids) == 60
    assert len(set(ids)) == 60


def test_area_filter_excludes_targets_in_other_areas(client_with_many_exceptions):
    body = client_with_many_exceptions.get(
        "/api/exceptions/list",
        params={"area_id": LIVING_ROOM, "page_size": 500},
    ).json()

    assert {r["device_id"] for r in body["exceptions"]} == {"d1"}


def test_entity_matches_the_area_inherited_from_its_device(client: TestClient):
    """`light.lamp` has no area of its own; its device `d1` is in Living Room.

    `/api/entities` treats that entity as being in Living Room, so this
    endpoint has to agree.
    """
    _ack_entity(client, "light.lamp", "inherited-area")

    body = client.get(
        "/api/exceptions/list", params={"area_id": LIVING_ROOM}
    ).json()

    assert [r["entity_id"] for r in body["exceptions"]] == ["light.lamp"]
    assert body["total"] == 1


def test_entity_matches_its_own_area(client: TestClient):
    """`light.kitchen_ceiling` sets its own area and has no device."""
    _ack_entity(client, "light.kitchen_ceiling", "own-area")

    body = client.get("/api/exceptions/list", params={"area_id": KITCHEN}).json()

    assert [r["entity_id"] for r in body["exceptions"]] == ["light.kitchen_ceiling"]


def test_area_filter_returns_both_kinds_together(client: TestClient):
    """A device and an entity in the same area must both come back.

    The two id sets have to be ORed: a row carries exactly one of them, so
    ANDing device and entity filters would match nothing.
    """
    _ack_device(client, "d1", "both-kinds")
    _ack_entity(client, "light.lamp", "both-kinds")

    body = client.get(
        "/api/exceptions/list", params={"area_id": LIVING_ROOM}
    ).json()

    assert body["total"] == 2
    assert {r["target_kind"] for r in body["exceptions"]} == {"device", "entity"}


def test_area_filter_combines_with_policy_id(client: TestClient):
    _ack_device(client, "d1", "wanted")
    _ack_device(client, "d1", "unwanted")
    _ack_device(client, "d2", "wanted")

    body = client.get(
        "/api/exceptions/list",
        params={"area_id": LIVING_ROOM, "policy_id": "wanted"},
    ).json()

    assert body["total"] == 1
    assert body["exceptions"][0]["device_id"] == "d1"
    assert body["exceptions"][0]["policy_id"] == "wanted"


def test_unknown_area_matches_nothing(client: TestClient):
    _ack_device(client, "d1", "p1")

    body = client.get(
        "/api/exceptions/list", params={"area_id": "no-such-area"}
    ).json()

    assert body["total"] == 0
    assert body["exceptions"] == []


def test_bulk_delete_reports_only_rows_that_existed(client: TestClient):
    """It used to echo back the ids it was asked to delete."""
    _ack_device(client, "d1", "real-1")
    _ack_device(client, "d1", "real-2")
    listed = client.get("/api/exceptions/list").json()["exceptions"]
    real_ids = sorted(r["id"] for r in listed)
    assert len(real_ids) == 2

    response = client.post(
        "/api/exceptions/bulk-delete", json={"ids": [*real_ids, 999_999]}
    )

    assert response.status_code == 200
    assert response.json()["deleted"] == real_ids
