"""GET /api/devices — filtered, paginated, issue-enriched device listing."""
import re
from collections import Counter
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from home_curator.api.deps import AppState, app_state
from home_curator.api.schemas import (
    AreaOut,
    AssignRoomResponse,
    AssignRoomResult,
    DeleteResponse,
    DeleteResult,
    DeviceOut,
    DevicesListResponse,
    EntitySummary,
    IssueOut,
    RenamePatternResponse,
    RenamePatternResult,
    RenameResponse,
)
from home_curator.ha_client.models import HADeviceUpdate
from home_curator.rules.base import Device, EvaluationContext, Issue, Severity
from home_curator.storage.db import session_scope
from home_curator.storage.exceptions_repo import ExceptionsRepo

router = APIRouter(prefix="/api", tags=["devices"])

SortBy = Literal["name", "room", "severity", "integration", "created", "modified"]

_ROOM_QUERY = Query(default_factory=list)
_ISSUE_TYPE_QUERY = Query(default_factory=list)
_INTEGRATION_QUERY = Query(default_factory=list)
_PAGE_QUERY = Query(default=1, ge=1)
_PAGE_SIZE_QUERY = Query(default=50, ge=1, le=500)
_APP_STATE_DEPENDENCY = Depends(app_state)

_SEVERITY_RANK: dict[Severity, int] = {"info": 1, "warning": 2, "error": 3}
_RANK_TO_SEVERITY: dict[int, Severity] = {v: k for k, v in _SEVERITY_RANK.items()}


class UpdateDeviceBody(BaseModel):
    name_by_user: str | None = None
    area_id: str | None = None

    model_config = {"extra": "forbid"}


class AssignRoomBody(BaseModel):
    device_ids: list[str]
    area_id: str


class RenamePatternBody(BaseModel):
    device_ids: list[str]
    pattern: str
    replacement: str
    dry_run: bool = True


class DeleteBody(BaseModel):
    device_ids: list[str]


def _matches_query(name: str, q: str, regex: bool) -> bool:
    if not q:
        return True
    if regex:
        try:
            return re.search(q, name) is not None
        except re.error:
            return False
    return q.lower() in name.lower()


def _highest_severity(issues: list[Issue]) -> Severity | None:
    if not issues:
        return None
    highest = max(_SEVERITY_RANK[i.severity] for i in issues)
    return _RANK_TO_SEVERITY[highest]


@router.get("/devices", response_model=DevicesListResponse)
def list_devices(
    q: str = "",
    regex: bool = False,
    room: list[str] = _ROOM_QUERY,
    issue_type: list[str] = _ISSUE_TYPE_QUERY,
    integration: list[str] = _INTEGRATION_QUERY,
    with_issues: bool = False,
    page: int = _PAGE_QUERY,
    page_size: int = _PAGE_SIZE_QUERY,
    sort_by: SortBy | None = None,
    sort_dir: Literal["asc", "desc"] = "asc",
    state: AppState = _APP_STATE_DEPENDENCY,
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
            created_at=d.created_at,
            modified_at=d.modified_at,
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
    integrations_set = set(integration)

    rows: list[tuple[Device, list[Issue]]] = []
    for d in hydrated:
        if not _matches_query(d.name, q, regex):
            continue
        if rooms_lower and (d.area_name or "").lower() not in rooms_lower:
            continue
        if integrations_set and (d.integration or "") not in integrations_set:
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
    integration_counts: Counter[str] = Counter()
    for d, issues in rows:
        for i in issues:
            counts[i.rule_type] += 1
        if d.area_name:
            area_counts[d.area_name] += 1
        if d.integration:
            integration_counts[d.integration] += 1

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
        elif sort_by == "integration":
            rows.sort(
                key=lambda r: (r[0].integration is None, (r[0].integration or "").lower()),
                reverse=reverse,
            )
        elif sort_by == "created":
            # Missing timestamps sort last on asc to mirror "no data at bottom".
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

    def _render(d: Device, issues: list[Issue]) -> DeviceOut:
        return DeviceOut(
            id=d.id,
            name=d.name_by_user or d.name,
            name_by_user=d.name_by_user,
            manufacturer=d.manufacturer,
            model=d.model,
            area_id=d.area_id,
            area_name=d.area_name,
            integration=d.integration,
            disabled_by=d.disabled_by,
            entities=[EntitySummary(id=e["id"], domain=e["domain"]) for e in d.entities],
            created_at=d.created_at,
            modified_at=d.modified_at,
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
    # Enumerate every integration seen across the unfiltered device set so
    # the filter dropdown lists all options regardless of current selection.
    all_integrations = sorted({d.integration for d in hydrated if d.integration})
    # Ensure every known option appears with a 0 where missing, so the
    # frontend can render dim zero-count entries without a second pass.
    full_area_counts = {a.name: area_counts.get(a.name, 0) for a in state.cache.areas()}
    full_issue_counts = {t: counts.get(t, 0) for t in all_issue_types}
    full_integration_counts = {i: integration_counts.get(i, 0) for i in all_integrations}

    return DevicesListResponse(
        devices=[_render(d, issues) for d, issues in page_rows],
        total=total,
        page=page,
        page_size=page_size,
        issue_counts_by_type=full_issue_counts,
        area_counts=full_area_counts,
        integration_counts=full_integration_counts,
        all_areas=all_areas,
        all_issue_types=all_issue_types,
        all_integrations=all_integrations,
    )


@router.patch("/devices/{device_id}", response_model=RenameResponse)
async def update_device(
    device_id: str,
    body: UpdateDeviceBody,
    state: AppState = _APP_STATE_DEPENDENCY,
) -> RenameResponse:
    """Partial update of a single device."""
    payload = body.model_dump(exclude_unset=True)
    if not payload:
        raise HTTPException(status_code=400, detail="no fields to update")
    try:
        await state.ha.update_device(device_id, HADeviceUpdate.model_validate(payload))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"ha update failed: {e}") from e
    return RenameResponse(ok=True)


@router.delete("/devices/{device_id}", response_model=RenameResponse)
async def delete_device(
    device_id: str,
    state: AppState = _APP_STATE_DEPENDENCY,
) -> RenameResponse:
    """Delete a single device via HA's remove_config_entry path."""
    if state.cache.device(device_id) is None:
        raise HTTPException(status_code=404, detail="device not found")
    try:
        await state.ha.delete_device(device_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"ha delete failed: {e}") from e
    return RenameResponse(ok=True)


@router.post("/devices/bulk-delete", response_model=DeleteResponse, response_model_exclude_none=True)
async def delete_devices_bulk(
    body: DeleteBody,
    state: AppState = _APP_STATE_DEPENDENCY,
) -> DeleteResponse:
    """Delete one or more devices. Returns per-device results for partial success."""
    if not body.device_ids:
        raise HTTPException(status_code=400, detail="device_ids must not be empty")
    results: list[DeleteResult] = []
    for did in body.device_ids:
        if state.cache.device(did) is None:
            results.append(DeleteResult(device_id=did, ok=False, error="device not found"))
            continue
        try:
            await state.ha.delete_device(did)
            results.append(DeleteResult(device_id=did, ok=True))
        except Exception as e:
            results.append(DeleteResult(device_id=did, ok=False, error=str(e)))
    return DeleteResponse(results=results)


@router.post(
    "/devices/assign-room",
    response_model=AssignRoomResponse,
    response_model_exclude_none=True,
)
async def assign_room(
    body: AssignRoomBody,
    state: AppState = _APP_STATE_DEPENDENCY,
) -> AssignRoomResponse:
    """Assign the given area_id to each device."""
    results: list[AssignRoomResult] = []
    for did in body.device_ids:
        try:
            await state.ha.update_device(did, HADeviceUpdate(area_id=body.area_id))
            results.append(AssignRoomResult(device_id=did, ok=True))
        except Exception as e:
            results.append(AssignRoomResult(device_id=did, ok=False, error=str(e)))
    return AssignRoomResponse(results=results)


@router.post("/devices/rename-pattern", response_model=RenamePatternResponse)
async def rename_pattern(
    body: RenamePatternBody,
    state: AppState = _APP_STATE_DEPENDENCY,
) -> RenamePatternResponse:
    """Regex find-and-replace across device names. Use dry_run=true to preview."""
    try:
        pat = re.compile(body.pattern)
    except re.error as e:
        return RenamePatternResponse(error=f"invalid regex: {e}", results=[])
    results: list[RenamePatternResult] = []
    for did in body.device_ids:
        d = state.cache.device(did)
        if d is None:
            results.append(RenamePatternResult(device_id=did, matched=False, reason="not in cache"))
            continue
        current = d.name_by_user or d.name
        new = pat.sub(body.replacement, current)
        if new == current:
            results.append(RenamePatternResult(device_id=did, matched=False))
            continue
        if body.dry_run:
            results.append(
                RenamePatternResult(
                    device_id=did,
                    matched=True,
                    new_name=new,
                    dry_run=True,
                )
            )
            continue
        try:
            await state.ha.update_device(did, HADeviceUpdate(name_by_user=new))
            results.append(
                RenamePatternResult(
                    device_id=did,
                    matched=True,
                    new_name=new,
                    ok=True,
                )
            )
        except Exception as e:
            results.append(
                RenamePatternResult(
                    device_id=did,
                    matched=True,
                    ok=False,
                    error=str(e),
                )
            )
    return RenamePatternResponse(results=results)
