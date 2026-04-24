"""GET /api/entities — filtered, paginated, issue-enriched entity listing.

Structural parallel to `devices.py`, reading from `state.entity_cache` and
dispatching the engine in `entities` scope.
"""
import re
from collections import Counter
from typing import Literal

from fastapi import APIRouter, Depends, Query

from home_curator.api.deps import AppState, app_state
from home_curator.api.schemas import (
    AreaOut,
    EntitiesListResponse,
    EntityOut,
    IssueOut,
)
from home_curator.rules.base import Entity, EvaluationContext, Issue, Severity
from home_curator.storage.db import session_scope
from home_curator.storage.exceptions_repo import ExceptionsRepo

router = APIRouter(prefix="/api", tags=["entities"])

_SEVERITY_RANK: dict[Severity, int] = {"info": 1, "warning": 2, "error": 3}
_RANK_TO_SEVERITY: dict[int, Severity] = {v: k for k, v in _SEVERITY_RANK.items()}

# The "no area" filter sentinel. Picked as a string unlikely to collide with
# any real area name (double-underscore + keyword) so users can still name a
# room "None" without conflicts.
NO_AREA_SENTINEL = "__none__"


def _matches_query(text: str, q: str, regex: bool) -> bool:
    if not q:
        return True
    if regex:
        try:
            return re.search(q, text) is not None
        except re.error:
            return False
    return q.lower() in text.lower()


def _highest_severity(issues: list[Issue]) -> Severity | None:
    if not issues:
        return None
    highest = max(_SEVERITY_RANK[i.severity] for i in issues)
    return _RANK_TO_SEVERITY[highest]


@router.get("/entities", response_model=EntitiesListResponse)
def list_entities(
    q: str = "",
    regex: bool = False,
    domain: list[str] = Query(default_factory=list),
    room: list[str] = Query(default_factory=list),
    integration: list[str] = Query(default_factory=list),
    issue_type: list[str] = Query(default_factory=list),
    with_issues: bool = False,
    show_disabled: bool = False,
    show_hidden: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    sort_by: Literal[
        "entity_id", "name", "domain", "room", "device",
        "integration", "severity", "created", "modified",
    ] | None = None,
    sort_dir: Literal["asc", "desc"] = "asc",
    state: AppState = Depends(app_state),
) -> EntitiesListResponse:
    """List entities with evaluated policy issues.

    Defaults: `show_disabled=false` and `show_hidden=false` — the UI's
    toggles flip these on explicitly. `room="__none__"` matches entities
    with no area assignment.
    """
    raw_entities = state.entity_cache.entities()

    # Device + area joins ahead of filtering so sorts on those keys work
    # and rendered rows carry the joined fields without a second lookup.
    devices_by_id = {d.id: d for d in state.cache.devices()}

    enriched: list[Entity] = list(raw_entities)

    with session_scope(state.session_factory) as session:
        exceptions = ExceptionsRepo(session).all_acknowledged_keys()
    ctx = EvaluationContext(
        area_name_to_id=state.cache.area_name_to_id(),
        area_id_to_name=state.cache.area_id_to_name(),
        exceptions=exceptions,
        # entity_naming_convention's "starts with device" check needs to
        # resolve the owning device's display name, so devices must be on
        # the ctx that's passed per-evaluation.
        devices_by_id=devices_by_id,
    )

    # Apply gating toggles first so they also influence the filter option
    # universes (all_* and *_counts).
    if not show_disabled:
        enriched = [e for e in enriched if e.disabled_by is None]
    if not show_hidden:
        enriched = [e for e in enriched if e.hidden_by is None]

    domains_set = set(domain)
    rooms_lower = {r.lower() for r in room}
    has_no_area_filter = any(r == NO_AREA_SENTINEL for r in room)
    rooms_without_sentinel = {r for r in rooms_lower if r != NO_AREA_SENTINEL.lower()}
    integrations_set = set(integration)
    issue_types_set = set(issue_type)

    def _room_match(e: Entity) -> bool:
        if not rooms_lower:
            return True
        if e.area_name is None:
            return has_no_area_filter
        return e.area_name.lower() in rooms_without_sentinel

    rows: list[tuple[Entity, list[Issue]]] = []
    for e in enriched:
        if not (
            _matches_query(e.entity_id, q, regex)
            or _matches_query(e.display_name, q, regex)
        ):
            continue
        if domains_set and e.domain not in domains_set:
            continue
        if not _room_match(e):
            continue
        if integrations_set and e.platform not in integrations_set:
            continue
        issues = state.engine.evaluate(e, ctx)
        if issue_types_set and not any(i.rule_type in issue_types_set for i in issues):
            continue
        if with_issues and not issues:
            continue
        rows.append((e, issues))

    total = len(rows)
    issue_counts: Counter[str] = Counter()
    domain_counts: Counter[str] = Counter()
    area_counts: Counter[str] = Counter()
    integration_counts: Counter[str] = Counter()
    for e, issues in rows:
        for i in issues:
            issue_counts[i.rule_type] += 1
        domain_counts[e.domain] += 1
        if e.area_name:
            area_counts[e.area_name] += 1
        if e.platform:
            integration_counts[e.platform] += 1

    if sort_by is not None:
        reverse = sort_dir == "desc"
        if sort_by == "entity_id":
            rows.sort(key=lambda r: r[0].entity_id.lower(), reverse=reverse)
        elif sort_by == "name":
            rows.sort(key=lambda r: r[0].display_name.lower(), reverse=reverse)
        elif sort_by == "domain":
            rows.sort(key=lambda r: r[0].domain.lower(), reverse=reverse)
        elif sort_by == "room":
            rows.sort(
                key=lambda r: (r[0].area_name is None, (r[0].area_name or "").lower()),
                reverse=reverse,
            )
        elif sort_by == "device":
            def _device_key(row: tuple[Entity, list[Issue]]) -> tuple[bool, str]:
                d = devices_by_id.get(row[0].device_id) if row[0].device_id else None
                name = ((d.name_by_user or d.name) if d else "") or ""
                return (d is None, name.lower())
            rows.sort(key=_device_key, reverse=reverse)
        elif sort_by == "integration":
            rows.sort(
                key=lambda r: (not r[0].platform, (r[0].platform or "").lower()),
                reverse=reverse,
            )
        elif sort_by == "severity":
            rows.sort(
                key=lambda r: (
                    max((_SEVERITY_RANK[i.severity] for i in r[1]), default=0),
                    len(r[1]),
                    r[0].display_name.lower(),
                ),
                reverse=reverse,
            )
        elif sort_by == "created":
            rows.sort(
                key=lambda r: (r[0].created_at is None, r[0].created_at or ""),
                reverse=reverse,
            )
        elif sort_by == "modified":
            rows.sort(
                key=lambda r: (r[0].modified_at is None, r[0].modified_at or ""),
                reverse=reverse,
            )

    start = (page - 1) * page_size
    end = start + page_size
    page_rows = rows[start:end]

    def _render(e: Entity, issues: list[Issue]) -> EntityOut:
        d = devices_by_id.get(e.device_id) if e.device_id else None
        device_name = (d.name_by_user or d.name) if d else None
        return EntityOut(
            entity_id=e.entity_id,
            name=e.name,
            original_name=e.original_name,
            display_name=e.display_name,
            domain=e.domain,
            platform=e.platform,
            device_id=e.device_id,
            device_name=device_name,
            area_id=e.area_id,
            area_name=e.area_name,
            disabled_by=e.disabled_by,
            hidden_by=e.hidden_by,
            icon=e.icon,
            created_at=e.created_at,
            modified_at=e.modified_at,
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

    # Universe enumerations: built from the gated (disabled/hidden) set so
    # the dropdowns never offer filters that would return zero regardless
    # of other selections. Entity-scope issue types read off the engine's
    # compiled rules.
    all_domains = sorted({e.domain for e in enriched})
    all_integrations = sorted({e.platform for e in enriched if e.platform})
    all_areas = [AreaOut(id=a.id, name=a.name) for a in state.cache.areas()]
    all_issue_types = sorted({
        r.rule_type for r in state.engine.compiled
        if getattr(r, "scope", "devices") == "entities"
    })

    full_domain_counts = {d: domain_counts.get(d, 0) for d in all_domains}
    full_area_counts = {a.name: area_counts.get(a.name, 0) for a in state.cache.areas()}
    full_integration_counts = {i: integration_counts.get(i, 0) for i in all_integrations}
    full_issue_counts = {t: issue_counts.get(t, 0) for t in all_issue_types}

    return EntitiesListResponse(
        entities=[_render(e, issues) for e, issues in page_rows],
        total=total,
        page=page,
        page_size=page_size,
        issue_counts_by_type=full_issue_counts,
        domain_counts=full_domain_counts,
        area_counts=full_area_counts,
        integration_counts=full_integration_counts,
        all_domains=all_domains,
        all_areas=all_areas,
        all_integrations=all_integrations,
        all_issue_types=all_issue_types,
    )
