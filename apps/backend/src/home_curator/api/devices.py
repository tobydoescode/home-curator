"""GET /api/devices — filtered, paginated, issue-enriched device listing."""
import re
from collections import Counter
from typing import Literal

from fastapi import APIRouter, Depends, Query

from home_curator.api.deps import AppState, app_state
from home_curator.api.schemas import (
    AreaOut,
    DeviceOut,
    DevicesListResponse,
    EntitySummary,
    IssueOut,
)
from home_curator.rules.base import Device, EvaluationContext, Issue
from home_curator.storage.db import session_scope
from home_curator.storage.exceptions_repo import ExceptionsRepo

router = APIRouter(prefix="/api", tags=["devices"])

_SEVERITY_RANK = {"info": 1, "warning": 2, "error": 3}
_RANK_TO_SEVERITY = {v: k for k, v in _SEVERITY_RANK.items()}


def _matches_query(name: str, q: str, regex: bool) -> bool:
    if not q:
        return True
    if regex:
        try:
            return re.search(q, name) is not None
        except re.error:
            return False
    return q.lower() in name.lower()


def _highest_severity(issues: list[Issue]) -> str | None:
    if not issues:
        return None
    highest = max(_SEVERITY_RANK[i.severity] for i in issues)
    return _RANK_TO_SEVERITY[highest]


@router.get("/devices", response_model=DevicesListResponse)
def list_devices(
    q: str = "",
    regex: bool = False,
    room: list[str] = Query(default_factory=list),
    issue_type: list[str] = Query(default_factory=list),
    with_issues: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    sort_by: Literal["name", "room", "severity"] | None = None,
    sort_dir: Literal["asc", "desc"] = "asc",
    state: AppState = Depends(app_state),
) -> DevicesListResponse:
    """List devices with evaluated policy issues.

    Filters: `q` (optionally `regex`), `room` (repeat to OR; matches area
    display name, case-insensitive), `issue_type` (repeat to OR; matches
    rule type), `with_issues` (only devices that have one or more issues).
    Results are paginated via `page` and `page_size`.
    """
    all_devices = state.cache.devices()
    tracker_state = state.tracker.all_state()
    hydrated = [
        Device(
            id=d.id,
            name=d.name,
            name_by_user=d.name_by_user,
            manufacturer=d.manufacturer,
            model=d.model,
            area_id=d.area_id,
            area_name=d.area_name,
            integration=d.integration,
            disabled_by=d.disabled_by,
            entities=d.entities,
            state=tracker_state.get(d.id, {}),
        )
        for d in all_devices
    ]
    with session_scope(state.session_factory) as session:
        exceptions = ExceptionsRepo(session).all_acknowledged_keys()
    ctx = EvaluationContext(
        area_name_to_id=state.cache.area_name_to_id(),
        area_id_to_name=state.cache.area_id_to_name(),
        exceptions=exceptions,
    )

    rooms_lower = {r.lower() for r in room}
    issue_types_set = set(issue_type)

    rows: list[tuple[Device, list[Issue]]] = []
    for d in hydrated:
        if not _matches_query(d.name, q, regex):
            continue
        if rooms_lower and (d.area_name or "").lower() not in rooms_lower:
            continue
        issues = state.engine.evaluate(d, ctx)
        if issue_types_set and not any(i.rule_type in issue_types_set for i in issues):
            continue
        if with_issues and not issues:
            continue
        rows.append((d, issues))

    total = len(rows)
    counts: Counter[str] = Counter()
    area_counts: Counter[str] = Counter()
    for d, issues in rows:
        for i in issues:
            counts[i.rule_type] += 1
        if d.area_name:
            area_counts[d.area_name] += 1

    if sort_by is not None:
        reverse = sort_dir == "desc"
        if sort_by == "name":
            rows.sort(key=lambda r: r[0].display_name.lower(), reverse=reverse)
        elif sort_by == "room":
            # Empty room sorts last on asc, first on desc — mirrors "no data"
            # convention where unassigned values drop to the bottom when sorting
            # naturally.
            rows.sort(
                key=lambda r: (r[0].area_name is None, (r[0].area_name or "").lower()),
                reverse=reverse,
            )
        elif sort_by == "severity":
            # Highest severity first on desc; tiebreak on issue count then name
            # so rows with the same severity don't shuffle.
            rows.sort(
                key=lambda r: (
                    max((_SEVERITY_RANK[i.severity] for i in r[1]), default=0),
                    len(r[1]),
                    r[0].display_name.lower(),
                ),
                reverse=reverse,
            )

    start = (page - 1) * page_size
    end = start + page_size
    page_rows = rows[start:end]

    def _render(d: Device, issues: list[Issue]) -> DeviceOut:
        return DeviceOut(
            id=d.id,
            name=d.name_by_user or d.name,
            manufacturer=d.manufacturer,
            model=d.model,
            area_id=d.area_id,
            area_name=d.area_name,
            integration=d.integration,
            disabled_by=d.disabled_by,
            entities=[EntitySummary(id=e["id"], domain=e["domain"]) for e in d.entities],
            issue_count=len(issues),
            highest_severity=_highest_severity(issues),
            issues=[
                IssueOut(
                    policy_id=i.policy_id,
                    rule_type=i.rule_type,
                    severity=i.severity,
                    message=i.message,
                )
                for i in issues
            ],
        )

    all_areas = [AreaOut(id=a.id, name=a.name) for a in state.cache.areas()]
    all_issue_types = sorted({r.rule_type for r in state.engine.compiled})
    # Ensure every known option appears with a 0 where missing, so the
    # frontend can render dim zero-count entries without a second pass.
    full_area_counts = {a.name: area_counts.get(a.name, 0) for a in state.cache.areas()}
    full_issue_counts = {t: counts.get(t, 0) for t in all_issue_types}

    return DevicesListResponse(
        devices=[_render(d, issues) for d, issues in page_rows],
        total=total,
        page=page,
        page_size=page_size,
        issue_counts_by_type=full_issue_counts,
        area_counts=full_area_counts,
        all_areas=all_areas,
        all_issue_types=all_issue_types,
    )
