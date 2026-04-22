from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from home_curator.api.deps import AppState, app_state
from home_curator.api.schemas import AcknowledgeResponse, BulkDeleteRequest, BulkDeleteResponse, ExceptionOut, ExceptionRow, ExceptionsListResponse
from home_curator.storage.db import session_scope
from home_curator.storage.exceptions_repo import ExceptionsRepo

router = APIRouter(prefix="/api/exceptions", tags=["exceptions"])


class AcknowledgeBody(BaseModel):
    device_id: str
    policy_id: str
    note: str | None = None
    acknowledged_by: str | None = None


@router.post("", status_code=status.HTTP_201_CREATED, response_model=AcknowledgeResponse)
def acknowledge(body: AcknowledgeBody, state: AppState = Depends(app_state)) -> AcknowledgeResponse:
    """Acknowledge (create or update) an exception for (device_id, policy_id)."""
    with session_scope(state.session_factory) as s:
        ExceptionsRepo(s).acknowledge(
            body.device_id,
            body.policy_id,
            note=body.note,
            acknowledged_by=body.acknowledged_by,
        )
    return AcknowledgeResponse(ok=True)


@router.delete("/{device_id}/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
def clear(device_id: str, policy_id: str, state: AppState = Depends(app_state)):
    """Remove an acknowledged exception for (device_id, policy_id)."""
    with session_scope(state.session_factory) as s:
        ExceptionsRepo(s).clear(device_id, policy_id)
    return None


@router.get("", response_model=list[ExceptionOut])
def list_for_device(device_id: str, state: AppState = Depends(app_state)) -> list[ExceptionOut]:
    """List all acknowledged exceptions for a device."""
    with session_scope(state.session_factory) as s:
        rows = ExceptionsRepo(s).for_device(device_id)
        return [
            ExceptionOut(
                device_id=r.device_id,
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
    policy_id: list[str] = Query(default_factory=list),
    device_id: list[str] = Query(default_factory=list),
    area_id: list[str] = Query(default_factory=list),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    state: AppState = Depends(app_state),
) -> ExceptionsListResponse:
    """Paginated list with filters and joined device/area fields.

    `area_id` filtering is applied post-fetch because area membership lives
    in the registry cache, not the SQLite row. `device_id` and `policy_id`
    filter at the DB layer.
    """
    with session_scope(state.session_factory) as s:
        rows, total = ExceptionsRepo(s).list_paginated(
            search=search,
            policy_ids=set(policy_id) if policy_id else None,
            device_ids=set(device_id) if device_id else None,
            page=page,
            page_size=page_size,
        )

    devices_by_id = {d.id: d for d in state.cache.devices()}
    if area_id:
        allowed = set(area_id)
        rows = [
            r for r in rows
            if (devices_by_id.get(r.device_id) and devices_by_id[r.device_id].area_id in allowed)
        ]
        total = len(rows)

    policy_names: dict[str, str] = {}
    if state.policies_file is not None:
        policy_names = {p.id: p.id for p in state.policies_file.policies}

    out: list[ExceptionRow] = []
    for r in rows:
        d = devices_by_id.get(r.device_id)
        out.append(ExceptionRow(
            id=r.id,
            device_id=r.device_id,
            device_name=(d.name_by_user or d.name) if d else None,
            device_area_name=(d.area_name if d else None),
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
async def bulk_delete(body: BulkDeleteRequest, state: AppState = Depends(app_state)) -> BulkDeleteResponse:
    """Delete multiple exceptions in one transaction and notify SSE subscribers."""
    ids = set(body.ids)
    with session_scope(state.session_factory) as s:
        deleted = ExceptionsRepo(s).bulk_delete(ids)
    if deleted > 0:
        await state.broker.publish({"kind": "exceptions_changed"})
    return BulkDeleteResponse(deleted=sorted(ids))
