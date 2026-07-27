"""Shared behaviour between the device and entity listing endpoints.

`devices.py` and `entities.py` are deliberately kept as separate pipelines —
they filter, sort and render different things, and merging them would mean a
function with five callbacks that reads worse than either original.

What lives here is the behaviour they must *agree* on. Every finding this
duplication has produced was a semantic disagreement rather than a mechanical
one: two endpoints differing on what "in an area" means, or on how missing
values sort. Those definitions belong in one place.
"""

import re
from collections.abc import Awaitable, Callable, Iterable

from home_curator.rules.base import Issue, Severity

SEVERITY_RANK: dict[Severity, int] = {"info": 1, "warning": 2, "error": 3}
RANK_TO_SEVERITY: dict[int, Severity] = {v: k for k, v in SEVERITY_RANK.items()}

def highest_severity(issues: list[Issue]) -> Severity | None:
    if not issues:
        return None
    return RANK_TO_SEVERITY[max(SEVERITY_RANK[i.severity] for i in issues)]


def severity_sort_key(issues: list[Issue]) -> tuple[int, int]:
    """Rank first, then issue count, so equal severities don't shuffle."""
    return (
        max((SEVERITY_RANK[i.severity] for i in issues), default=0),
        len(issues),
    )


def matches_query(text: str, q: str, regex: bool) -> bool:
    """Substring match, or regex when asked. An invalid regex matches nothing.

    Rejecting rather than raising keeps a half-typed pattern in the search box
    from 500ing the listing.
    """
    if not q:
        return True
    if regex:
        try:
            return re.search(q, text) is not None
        except re.error:
            return False
    return q.lower() in text.lower()


def missing_last(value: str | None) -> tuple[bool, str]:
    """Sort key placing unset values after set ones, compared case-insensitively.

    Ascending puts "no data" at the bottom, which is what every column in both
    tables wants. Writing this inline per column is how `entities.py` ended up
    testing `not platform` where its neighbours tested `is None` — same result
    for `None`, different for an empty string.
    """
    return (value is None, (value or "").lower())


def missing_last_exact(value: str | None) -> tuple[bool, str]:
    """`missing_last` without case folding, for values that are already
    canonical — ISO-8601 timestamps, where lowercasing is meaningless."""
    return (value is None, value or "")


async def per_item_results[R](
    ids: Iterable[str],
    action: Callable[[str], Awaitable[None]],
    *,
    build: Callable[[str, bool, str | None], R],
    precheck: Callable[[str], str | None] | None = None,
) -> list[R]:
    """Apply `action` to each id, collecting a per-id outcome.

    Bulk operations report partial success rather than failing the batch, so
    one refused device does not silently abandon the rest. `build(id, ok,
    error)` turns each outcome into the endpoint's own result model.

    `precheck` returns a reason to fail an id without attempting the action —
    "not found" cases, which would otherwise reach Home Assistant only to be
    rejected there.
    """
    results: list[R] = []
    for id_ in ids:
        if precheck is not None:
            reason = precheck(id_)
            if reason is not None:
                results.append(build(id_, False, reason))
                continue
        try:
            await action(id_)
        except Exception as e:  # noqa: BLE001 - reported per item, not swallowed
            results.append(build(id_, False, str(e)))
        else:
            results.append(build(id_, True, None))
    return results
