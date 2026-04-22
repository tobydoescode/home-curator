import re
from collections import Counter

from fastapi import APIRouter, Depends, Query

from home_curator.api.deps import AppState, app_state
from home_curator.rules.base import Device, EvaluationContext
from home_curator.storage.db import session_scope
from home_curator.storage.exceptions_repo import ExceptionsRepo

router = APIRouter(prefix="/api", tags=["devices"])


def _matches_query(name: str, q: str, regex: bool) -> bool:
    if not q:
        return True
    if regex:
        try:
            return re.search(q, name) is not None
        except re.error:
            return False
    return q.lower() in name.lower()


def _evaluate(state: AppState, device: Device, ctx: EvaluationContext):
    return state.engine.evaluate(device, ctx)


@router.get("/devices")
def list_devices(
    q: str = "",
    regex: bool = False,
    room: str | None = None,
    issue_type: str | None = None,
    with_issues: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    state: AppState = Depends(app_state),
):
    all_devices = state.cache.devices()
    tracker_state = state.tracker.all_state()
    # Inject state into devices
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

    rows = []
    for d in hydrated:
        if not _matches_query(d.name, q, regex):
            continue
        if room is not None and (d.area_name or "").lower() != room.lower():
            continue
        issues = _evaluate(state, d, ctx)
        if issue_type is not None and not any(i.rule_type == issue_type for i in issues):
            continue
        if with_issues and not issues:
            continue
        rows.append((d, issues))

    total = len(rows)
    counts: Counter[str] = Counter()
    for _, issues in rows:
        for i in issues:
            counts[i.rule_type] += 1
    start = (page - 1) * page_size
    end = start + page_size
    page_rows = rows[start:end]

    def _render(d: Device, issues):
        severity_rank = {"info": 1, "warning": 2, "error": 3}
        highest = max((severity_rank[i.severity] for i in issues), default=0)
        highest_name = {v: k for k, v in severity_rank.items()}.get(highest)
        return {
            "id": d.id,
            "name": d.name_by_user or d.name,
            "manufacturer": d.manufacturer,
            "model": d.model,
            "area_id": d.area_id,
            "area_name": d.area_name,
            "integration": d.integration,
            "disabled_by": d.disabled_by,
            "entities": d.entities,
            "issue_count": len(issues),
            "highest_severity": highest_name,
            "issues": [
                {
                    "policy_id": i.policy_id,
                    "rule_type": i.rule_type,
                    "severity": i.severity,
                    "message": i.message,
                }
                for i in issues
            ],
        }

    return {
        "devices": [_render(d, issues) for d, issues in page_rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "issue_counts_by_type": dict(counts),
    }
