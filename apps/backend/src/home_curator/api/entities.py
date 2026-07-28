"""GET /api/entities — filtered, paginated, issue-enriched entity listing.

Structural parallel to `devices.py`, reading from `state.entity_cache` and
dispatching the engine in `entities` scope.
"""
from collections import Counter
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from home_curator.api.deps import AppState, app_state
from home_curator.api.listing import (
    highest_severity,
    matches_query,
    missing_last,
    missing_last_exact,
    per_item_results,
    severity_sort_key,
)
from home_curator.api.schemas import (
    AreaOut,
    AssignRoomEntityResponse,
    AssignRoomEntityResult,
    DeleteEntityResponse,
    DeleteEntityResult,
    EntitiesListResponse,
    EntityOut,
    EntityStateResponse,
    EntityStateResult,
    IssueOut,
    RenamePatternEntityResponse,
    RenamePatternEntityResult,
    RenameResponse,
)
from home_curator.ha_client.models import HAEntityUpdate
from home_curator.rules.base import Entity, EvaluationContext, Issue
from home_curator.storage.db import session_scope
from home_curator.storage.exceptions_repo import ExceptionsRepo
from home_curator.user_regex import UserPatternError, compile_user_pattern

router = APIRouter(prefix="/api", tags=["entities"])
_APP_STATE_DEPENDENCY = Depends(app_state)
_DOMAIN_QUERY = Query(default_factory=list)
_ROOM_QUERY = Query(default_factory=list)
_INTEGRATION_QUERY = Query(default_factory=list)
_ISSUE_TYPE_QUERY = Query(default_factory=list)
_PAGE_QUERY = Query(default=1, ge=1)
_PAGE_SIZE_QUERY = Query(default=50, ge=1, le=500)

# The "no area" filter sentinel. Picked as a string unlikely to collide with
# any real area name (double-underscore + keyword) so users can still name a
# room "None" without conflicts.
NO_AREA_SENTINEL = "__none__"


class UpdateEntityBody(BaseModel):
    """Partial entity update."""

    new_entity_id: str | None = None
    name: str | None = None
    area_id: str | None = None
    disabled_by: str | None = None
    hidden_by: str | None = None
    icon: str | None = None

    model_config = {"extra": "forbid"}


class AssignRoomEntitiesBody(BaseModel):
    entity_ids: list[str]
    area_id: str | None


class RenamePatternEntitiesBody(BaseModel):
    entity_ids: list[str]
    id_pattern: str | None = None
    id_replacement: str | None = None
    name_pattern: str | None = None
    name_replacement: str | None = None
    dry_run: bool = True


class EntityStateBody(BaseModel):
    """Bulk enable / disable / show / hide."""

    entity_ids: list[str]
    field: Literal["disabled_by", "hidden_by"]
    value: Literal["user"] | None


class DeleteEntityBody(BaseModel):
    entity_ids: list[str]


@router.get("/entities", response_model=EntitiesListResponse)
def list_entities(
    q: str = "",
    regex: bool = False,
    domain: list[str] = _DOMAIN_QUERY,
    room: list[str] = _ROOM_QUERY,
    integration: list[str] = _INTEGRATION_QUERY,
    issue_type: list[str] = _ISSUE_TYPE_QUERY,
    with_issues: bool = False,
    show_disabled: bool = False,
    show_hidden: bool = False,
    page: int = _PAGE_QUERY,
    page_size: int = _PAGE_SIZE_QUERY,
    sort_by: Literal[
        "entity_id", "name", "domain", "room", "device",
        "integration", "severity", "created", "modified",
    ] | None = None,
    sort_dir: Literal["asc", "desc"] = "asc",
    state: AppState = _APP_STATE_DEPENDENCY,
) -> EntitiesListResponse:
    """List entities with evaluated policy issues.

    Defaults: `show_disabled=false` and `show_hidden=false` — the UI's
    toggles flip these on explicitly. `room="__none__"` matches entities
    with no area assignment.
    """
    raw_entities = state.entity_cache.entities()

    # Devices are looked up per row by `_render` and by the `device` sort key;
    # this is the index they share.
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
            matches_query(e.entity_id, q, regex)
            or matches_query(e.display_name, q, regex)
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
            rows.sort(key=lambda r: missing_last(r[0].area_name), reverse=reverse)
        elif sort_by == "device":
            def _device_key(row: tuple[Entity, list[Issue]]) -> tuple[bool, str]:
                d = devices_by_id.get(row[0].device_id) if row[0].device_id else None
                name = ((d.name_by_user or d.name) if d else "") or ""
                return (d is None, name.lower())
            rows.sort(key=_device_key, reverse=reverse)
        elif sort_by == "integration":
            rows.sort(key=lambda r: missing_last(r[0].platform), reverse=reverse)
        elif sort_by == "severity":
            rows.sort(
                key=lambda r: (*severity_sort_key(r[1]), r[0].display_name.lower()),
                reverse=reverse,
            )
        elif sort_by == "created":
            rows.sort(key=lambda r: missing_last_exact(r[0].created_at), reverse=reverse)
        elif sort_by == "modified":
            rows.sort(key=lambda r: missing_last_exact(r[0].modified_at), reverse=reverse)

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
            highest_severity=highest_severity(issues),
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


@router.patch("/entities/{entity_id}", response_model=RenameResponse)
async def update_entity(
    entity_id: str,
    body: UpdateEntityBody,
    state: AppState = _APP_STATE_DEPENDENCY,
) -> RenameResponse:
    """Partial update of a single entity."""
    payload = body.model_dump(exclude_unset=True)
    if not payload:
        raise HTTPException(status_code=400, detail="no fields to update")
    try:
        await state.ha.update_entity(entity_id, HAEntityUpdate.model_validate(payload))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"ha update failed: {e}") from e
    return RenameResponse(ok=True)


@router.delete("/entities/{entity_id}", response_model=RenameResponse)
async def delete_entity(
    entity_id: str,
    state: AppState = _APP_STATE_DEPENDENCY,
) -> RenameResponse:
    """Delete a single entity via HA's entity_registry/remove."""
    if state.entity_cache.entity(entity_id) is None:
        raise HTTPException(status_code=404, detail="entity not found")
    try:
        await state.ha.delete_entity(entity_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"ha delete failed: {e}") from e
    return RenameResponse(ok=True)


@router.post(
    "/entities/bulk-delete",
    response_model=DeleteEntityResponse,
    response_model_exclude_none=True,
)
async def delete_entities_bulk(
    body: DeleteEntityBody,
    state: AppState = _APP_STATE_DEPENDENCY,
) -> DeleteEntityResponse:
    """Delete one or more entities. Returns per-entity results for partial success."""
    if not body.entity_ids:
        raise HTTPException(status_code=400, detail="entity_ids must not be empty")
    results = await per_item_results(
        body.entity_ids,
        state.ha.delete_entity,
        build=lambda eid, ok, error: DeleteEntityResult(
            entity_id=eid, ok=ok, error=error
        ),
        precheck=lambda eid: (
            None if state.entity_cache.entity(eid) is not None else "entity not found"
        ),
    )
    return DeleteEntityResponse(results=results)


@router.post(
    "/entities/assign-room",
    response_model=AssignRoomEntityResponse,
    response_model_exclude_none=True,
)
async def assign_room_entities(
    body: AssignRoomEntitiesBody,
    state: AppState = _APP_STATE_DEPENDENCY,
) -> AssignRoomEntityResponse:
    """Bulk-assign an area_id to one or more entities."""
    results = await per_item_results(
        body.entity_ids,
        lambda eid: state.ha.update_entity(eid, HAEntityUpdate(area_id=body.area_id)),
        build=lambda eid, ok, error: AssignRoomEntityResult(
            entity_id=eid, ok=ok, error=error
        ),
    )
    return AssignRoomEntityResponse(results=results)


@router.post(
    "/entities/rename-pattern",
    response_model=RenamePatternEntityResponse,
    response_model_exclude_none=False,
)
async def rename_pattern_entities(
    body: RenamePatternEntitiesBody,
    state: AppState = _APP_STATE_DEPENDENCY,
) -> RenamePatternEntityResponse:
    """Dual-regex rename across entity_id and / or friendly name."""
    id_pat = None
    name_pat = None
    if body.id_pattern is not None:
        try:
            id_pat = compile_user_pattern(body.id_pattern)
        except UserPatternError as e:
            return RenamePatternEntityResponse(
                results=[], error=f"invalid id_pattern: {e}",
            )
    if body.name_pattern is not None:
        try:
            name_pat = compile_user_pattern(body.name_pattern)
        except UserPatternError as e:
            return RenamePatternEntityResponse(
                results=[], error=f"invalid name_pattern: {e}",
            )
    if id_pat is None and name_pat is None:
        return RenamePatternEntityResponse(
            results=[], error="provide at least one of id_pattern or name_pattern",
        )

    results: list[RenamePatternEntityResult] = []
    for eid in body.entity_ids:
        # Not `e`: this function already binds that name as an `except ... as e`
        # target above, and Python deletes such a target at the end of its
        # block, so reusing it here gave the name two meanings in one scope.
        entity = state.entity_cache.entity(eid)
        if entity is None:
            results.append(
                RenamePatternEntityResult(
                    entity_id=eid,
                    id_changed=False,
                    name_changed=False,
                    ok=False,
                    dry_run=body.dry_run,
                    error="entity not found",
                )
            )
            continue

        new_id: str | None = None
        id_changed = False
        if id_pat is not None and body.id_replacement is not None:
            proposed = id_pat.sub(body.id_replacement, eid)
            if proposed != eid:
                new_id = proposed
                id_changed = True

        new_name: str | None = None
        name_changed = False
        if name_pat is not None and body.name_replacement is not None:
            current = entity.display_name
            proposed_name = name_pat.sub(body.name_replacement, current)
            if proposed_name != current:
                new_name = proposed_name
                name_changed = True

        if not (id_changed or name_changed):
            results.append(
                RenamePatternEntityResult(
                    entity_id=eid,
                    id_changed=False,
                    new_entity_id=None,
                    name_changed=False,
                    new_name=None,
                    ok=True,
                    dry_run=body.dry_run,
                    error=None,
                )
            )
            continue

        if body.dry_run:
            results.append(
                RenamePatternEntityResult(
                    entity_id=eid,
                    id_changed=id_changed,
                    new_entity_id=new_id,
                    name_changed=name_changed,
                    new_name=new_name,
                    ok=True,
                    dry_run=True,
                    error=None,
                )
            )
            continue

        changes = HAEntityUpdate(
            **({"new_entity_id": new_id} if id_changed and new_id is not None else {}),
            **({"name": new_name} if name_changed and new_name is not None else {}),
        )
        try:
            await state.ha.update_entity(eid, changes)
            results.append(
                RenamePatternEntityResult(
                    entity_id=eid,
                    id_changed=id_changed,
                    new_entity_id=new_id,
                    name_changed=name_changed,
                    new_name=new_name,
                    ok=True,
                    dry_run=False,
                    error=None,
                )
            )
        except Exception as ex:
            results.append(
                RenamePatternEntityResult(
                    entity_id=eid,
                    id_changed=id_changed,
                    new_entity_id=new_id,
                    name_changed=name_changed,
                    new_name=new_name,
                    ok=False,
                    dry_run=False,
                    error=str(ex),
                )
            )
    return RenamePatternEntityResponse(results=results, error=None)


@router.post(
    "/entities/state",
    response_model=EntityStateResponse,
    response_model_exclude_none=True,
)
async def entity_state(
    body: EntityStateBody,
    state: AppState = _APP_STATE_DEPENDENCY,
) -> EntityStateResponse:
    """Bulk flip disabled_by / hidden_by to user or None."""
    if not body.entity_ids:
        raise HTTPException(status_code=400, detail="entity_ids must not be empty")
    results = await per_item_results(
        body.entity_ids,
        lambda eid: state.ha.update_entity(
            eid, HAEntityUpdate(**{body.field: body.value})
        ),
        build=lambda eid, ok, error: EntityStateResult(
            entity_id=eid, ok=ok, error=error
        ),
    )
    return EntityStateResponse(results=results)
