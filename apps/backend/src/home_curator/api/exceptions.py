from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, model_validator

from home_curator.api.deps import AppState, app_state
from home_curator.api.schemas import AcknowledgeResponse, BulkDeleteRequest, BulkDeleteResponse, ExceptionOut, ExceptionRow, ExceptionsListResponse
from home_curator.storage.db import session_scope
from home_curator.storage.exceptions_repo import ExceptionsRepo

router = APIRouter(prefix="/api/exceptions", tags=["exceptions"])
_APP_STATE_DEPENDENCY = Depends(app_state)
_POLICY_ID_QUERY = Query(default_factory=list)
_DEVICE_ID_QUERY = Query(default_factory=list)
_ENTITY_ID_QUERY = Query(default_factory=list)
_AREA_ID_QUERY = Query(default_factory=list)
_PAGE_QUERY = Query(default=1, ge=1)
_PAGE_SIZE_QUERY = Query(default=50, ge=1, le=500)


class AcknowledgeBody(BaseModel):
    device_id: str | None = None
    entity_id: str | None = None
    policy_id: str
    note: str | None = None
    acknowledged_by: str | None = None

    @model_validator(mode="after")
    def _exactly_one_target(self):
        if (self.device_id is None) == (self.entity_id is None):
            raise ValueError(
                "exactly one of device_id / entity_id is required",
            )
        return self


@router.post("", status_code=status.HTTP_201_CREATED, response_model=AcknowledgeResponse)
def acknowledge(
    body: AcknowledgeBody,
    state: AppState = _APP_STATE_DEPENDENCY,
) -> AcknowledgeResponse:
    """Acknowledge (create or update) an exception for either a device or entity target."""
    with session_scope(state.session_factory) as s:
        repo = ExceptionsRepo(s)
        if body.device_id is not None:
            repo.acknowledge(
                body.device_id,
                body.policy_id,
                note=body.note,
                acknowledged_by=body.acknowledged_by,
            )
        else:
            assert body.entity_id is not None  # validator above guarantees this
            repo.ack_entity(
                body.entity_id,
                body.policy_id,
                note=body.note,
                acknowledged_by=body.acknowledged_by,
            )
    return AcknowledgeResponse(ok=True)


@router.delete("/{device_id}/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
def clear(device_id: str, policy_id: str, state: AppState = _APP_STATE_DEPENDENCY):
    """Remove an acknowledged exception for (device_id, policy_id)."""
    with session_scope(state.session_factory) as s:
        ExceptionsRepo(s).clear(device_id, policy_id)
    return None


@router.delete("/entity/{entity_id}/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
def clear_entity(entity_id: str, policy_id: str, state: AppState = _APP_STATE_DEPENDENCY):
    """Remove an acknowledged exception for (entity_id, policy_id). No-op if absent."""
    with session_scope(state.session_factory) as s:
        ExceptionsRepo(s).clear_entity(entity_id, policy_id)
    return None


@router.get("", response_model=list[ExceptionOut])
def list_for_device(
    device_id: str,
    state: AppState = _APP_STATE_DEPENDENCY,
) -> list[ExceptionOut]:
    """List all acknowledged exceptions for a device."""
    with session_scope(state.session_factory) as s:
        rows = ExceptionsRepo(s).for_device(device_id)
        # `for_device` filters on device_id == the argument, so device_id is
        # guaranteed non-null on every returned row — narrow for the type checker.
        return [
            ExceptionOut(
                device_id=r.device_id or device_id,
                policy_id=r.policy_id,
                acknowledged_at=r.acknowledged_at.isoformat(),
                acknowledged_by=r.acknowledged_by,
                note=r.note,
            )
            for r in rows
        ]


@router.get("/list", response_model=ExceptionsListResponse)
def list_paginated(
    search: str | None = None,
    policy_id: list[str] = _POLICY_ID_QUERY,
    device_id: list[str] = _DEVICE_ID_QUERY,
    entity_id: list[str] = _ENTITY_ID_QUERY,
    area_id: list[str] = _AREA_ID_QUERY,
    page: int = _PAGE_QUERY,
    page_size: int = _PAGE_SIZE_QUERY,
    state: AppState = _APP_STATE_DEPENDENCY,
) -> ExceptionsListResponse:
    """Paginated cross-kind exception list.

    Filters are ANDed. Passing `device_id` restricts to device-kind rows;
    passing `entity_id` restricts to entity-kind rows; passing neither
    returns both kinds. `area_id` joins the device or entity cache
    post-fetch since area membership lives there, not the SQLite row.
    """
    with session_scope(state.session_factory) as s:
        rows, total = ExceptionsRepo(s).list_paginated(
            search=search,
            policy_ids=set(policy_id) if policy_id else None,
            device_ids=set(device_id) if device_id else None,
            entity_ids=set(entity_id) if entity_id else None,
            page=page,
            page_size=page_size,
        )

    devices_by_id = {d.id: d for d in state.cache.devices()}
    area_id_to_name = state.cache.area_id_to_name()
    entities_by_id = (
        {e.entity_id: e for e in state.entity_cache.entities()}
        if state.entity_cache is not None else {}
    )

    if area_id:
        allowed = set(area_id)
        filtered = []
        for r in rows:
            if r.device_id is not None:
                d = devices_by_id.get(r.device_id)
                if d is not None and d.area_id in allowed:
                    filtered.append(r)
            elif r.entity_id is not None:
                e = entities_by_id.get(r.entity_id)
                if e is not None and e.area_id in allowed:
                    filtered.append(r)
        rows = filtered
        total = len(rows)

    policy_names: dict[str, str] = {}
    if state.policies_file is not None:
        policy_names = {p.id: p.id for p in state.policies_file.policies}

    out: list[ExceptionRow] = []
    for r in rows:
        if r.device_id is not None:
            d = devices_by_id.get(r.device_id)
            name = (d.name_by_user or d.name) if d else None
            area_name = d.area_name if d else None
            out.append(ExceptionRow(
                id=r.id,
                target_kind="device",
                device_id=r.device_id,
                entity_id=None,
                target_name=name,
                target_area_name=area_name,
                device_name=name,
                device_area_name=area_name,
                policy_id=r.policy_id,
                policy_name=policy_names.get(r.policy_id, r.policy_id),
                acknowledged_at=r.acknowledged_at.isoformat(),
                acknowledged_by=r.acknowledged_by,
                note=r.note,
            ))
        else:
            e = entities_by_id.get(r.entity_id) if r.entity_id is not None else None
            display = e.display_name if e is not None else None
            ent_area_id = e.area_id if e is not None else None
            target_area_name = area_id_to_name.get(ent_area_id) if ent_area_id else None
            out.append(ExceptionRow(
                id=r.id,
                target_kind="entity",
                device_id=None,
                entity_id=r.entity_id,
                target_name=display,
                target_area_name=target_area_name,
                policy_id=r.policy_id,
                policy_name=policy_names.get(r.policy_id, r.policy_id),
                acknowledged_at=r.acknowledged_at.isoformat(),
                acknowledged_by=r.acknowledged_by,
                note=r.note,
            ))
    return ExceptionsListResponse(
        exceptions=out, total=total, page=page, page_size=page_size,
    )


@router.post("/bulk-delete", response_model=BulkDeleteResponse)
async def bulk_delete(
    body: BulkDeleteRequest,
    state: AppState = _APP_STATE_DEPENDENCY,
) -> BulkDeleteResponse:
    """Delete multiple exceptions in one transaction and notify SSE subscribers."""
    ids = set(body.ids)
    with session_scope(state.session_factory) as s:
        deleted = ExceptionsRepo(s).bulk_delete(ids)
    if deleted > 0:
        await state.broker.publish({"kind": "exceptions_changed"})
    return BulkDeleteResponse(deleted=sorted(ids))
