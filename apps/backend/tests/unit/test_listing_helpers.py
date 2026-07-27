"""The behaviour the device and entity listings have to agree on.

These were duplicated per endpoint, and had already drifted: the entity
listing sorted `platform` with `not r[0].platform` where every neighbouring
column used `is None`. Identical for `None`, different for `""`.
"""

import pytest

from home_curator.api.listing import (
    highest_severity,
    matches_query,
    missing_last,
    missing_last_exact,
    per_item_results,
    severity_sort_key,
)
from home_curator.rules.base import Issue


def _issue(severity: str) -> Issue:
    return Issue(
        policy_id="p",
        rule_type="t",
        severity=severity,  # type: ignore[arg-type]
        message="m",
        target_kind="device",
        target_id="d1",
    )


# --- severity ------------------------------------------------------------


def test_highest_severity_of_nothing_is_none():
    assert highest_severity([]) is None


@pytest.mark.parametrize(
    ("severities", "expected"),
    [
        (["info"], "info"),
        (["info", "warning"], "warning"),
        (["warning", "error", "info"], "error"),
    ],
)
def test_highest_severity_picks_the_worst(severities, expected):
    assert highest_severity([_issue(s) for s in severities]) == expected


def test_severity_sort_key_breaks_ties_on_count():
    one_error = severity_sort_key([_issue("error")])
    two_errors = severity_sort_key([_issue("error"), _issue("info")])
    assert two_errors > one_error


def test_severity_sort_key_of_nothing_ranks_lowest():
    assert severity_sort_key([]) < severity_sort_key([_issue("info")])


# --- query matching ------------------------------------------------------


def test_empty_query_matches_everything():
    assert matches_query("anything", "", regex=False)


def test_plain_query_is_case_insensitive_substring():
    assert matches_query("Living Room Lamp", "room", regex=False)
    assert not matches_query("Living Room Lamp", "kitchen", regex=False)


def test_regex_query_matches():
    assert matches_query("kitchen_light", "^kitchen_", regex=True)
    assert not matches_query("hall_light", "^kitchen_", regex=True)


def test_invalid_regex_matches_nothing_rather_than_raising():
    """A half-typed pattern in the search box must not 500 the listing."""
    assert not matches_query("anything", "[", regex=True)


# --- sort keys -----------------------------------------------------------


def test_missing_sorts_after_present():
    assert missing_last(None) > missing_last("zzz")


def test_missing_last_is_case_insensitive():
    assert missing_last("Kitchen") < missing_last("living room")


def test_empty_string_is_treated_as_present():
    """The drifted copy used a truthiness check, which put "" with the nulls."""
    assert missing_last("") < missing_last(None)


def test_missing_last_exact_does_not_case_fold():
    # ISO-8601 timestamps are already canonical; lowercasing is meaningless.
    assert missing_last_exact("2026-01-02T00:00:00+00:00") > missing_last_exact(
        "2026-01-01T00:00:00+00:00"
    )
    assert missing_last_exact(None) > missing_last_exact("2026-01-02T00:00:00+00:00")


# --- bulk results --------------------------------------------------------


def _build(id_: str, ok: bool, error: str | None) -> dict[str, object]:
    return {"id": id_, "ok": ok, "error": error}


async def test_per_item_reports_each_outcome_separately():
    """One failure must not abandon the rest of the batch."""

    async def action(id_: str) -> None:
        if id_ == "bad":
            raise RuntimeError("refused by HA")

    results = await per_item_results(["a", "bad", "c"], action, build=_build)

    assert results == [
        {"id": "a", "ok": True, "error": None},
        {"id": "bad", "ok": False, "error": "refused by HA"},
        {"id": "c", "ok": True, "error": None},
    ]


async def test_precheck_short_circuits_without_calling_the_action():
    called: list[str] = []

    async def action(id_: str) -> None:
        called.append(id_)

    results = await per_item_results(
        ["known", "missing"],
        action,
        build=_build,
        precheck=lambda i: None if i == "known" else "not found",
    )

    assert called == ["known"]
    assert results[1] == {"id": "missing", "ok": False, "error": "not found"}


async def test_no_ids_is_an_empty_result_not_an_error():
    async def action(id_: str) -> None:
        raise AssertionError("should not be called")

    assert await per_item_results([], action, build=_build) == []
