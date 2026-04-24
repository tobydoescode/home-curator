import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from home_curator.api.deps import AppState, app_state
from home_curator.api.schemas import (
    AssignRoomEntityResponse,
    AssignRoomEntityResult,
    AssignRoomResponse,
    AssignRoomResult,
    DeleteEntityResponse,
    DeleteEntityResult,
    DeleteResponse,
    DeleteResult,
    EntityStateResponse,
    EntityStateResult,
    RenamePatternEntityResponse,
    RenamePatternEntityResult,
    RenamePatternResponse,
    RenamePatternResult,
    RenameResponse,
)
from home_curator.ha_client.models import HADeviceUpdate, HAEntityUpdate

router = APIRouter(prefix="/api/actions", tags=["actions"])
_APP_STATE_DEPENDENCY = Depends(app_state)


class AssignRoomBody(BaseModel):
    device_ids: list[str]
    area_id: str


class RenameBody(BaseModel):
    device_id: str
    name_by_user: str


class RenamePatternBody(BaseModel):
    device_ids: list[str]
    pattern: str
    replacement: str
    dry_run: bool = True


class UpdateDeviceBody(BaseModel):
    # Both fields optional — the PATCH accepts any subset. Missing keys are
    # omitted from the HA payload; `None` is meaningful and forwarded (e.g.
    # `area_id: null` to clear the room assignment).
    name_by_user: str | None = None
    area_id: str | None = None

    model_config = {"extra": "forbid"}


class UpdateEntityBody(BaseModel):
    """Partial entity update.

    `new_entity_id` renames the HA slug; all other fields map 1:1 onto
    `config/entity_registry/update`. `None` is meaningful for `area_id`,
    `disabled_by`, `hidden_by`, `icon` (it clears the value in HA) — missing
    keys are omitted from the payload.
    """

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


class DeleteBody(BaseModel):
    device_ids: list[str]


class DeleteEntityBody(BaseModel):
    entity_ids: list[str]


@router.post("/assign-room", response_model=AssignRoomResponse, response_model_exclude_none=True)
async def assign_room(
    body: AssignRoomBody,
    state: AppState = _APP_STATE_DEPENDENCY,
) -> AssignRoomResponse:
    """Assign the given `area_id` to each device."""
    results = []
    for did in body.device_ids:
        try:
            await state.ha.update_device(did, HADeviceUpdate(area_id=body.area_id))
            results.append(AssignRoomResult(device_id=did, ok=True))
        except Exception as e:
            results.append(AssignRoomResult(device_id=did, ok=False, error=str(e)))
    return AssignRoomResponse(results=results)


@router.post("/rename", response_model=RenameResponse)
async def rename(body: RenameBody, state: AppState = _APP_STATE_DEPENDENCY) -> RenameResponse:
    """Rename a single device via `name_by_user`."""
    await state.ha.update_device(body.device_id, HADeviceUpdate(name_by_user=body.name_by_user))
    return RenameResponse(ok=True)


@router.post("/rename-pattern", response_model=RenamePatternResponse)
async def rename_pattern(
    body: RenamePatternBody,
    state: AppState = _APP_STATE_DEPENDENCY,
) -> RenamePatternResponse:
    """Regex find-and-replace across device names. Use `dry_run=true` to preview."""
    try:
        pat = re.compile(body.pattern)
    except re.error as e:
        return RenamePatternResponse(error=f"invalid regex: {e}", results=[])
    results = []
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
        else:
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


@router.patch("/device/{device_id}", response_model=RenameResponse)
async def update_device(
    device_id: str,
    body: UpdateDeviceBody,
    state: AppState = _APP_STATE_DEPENDENCY,
) -> RenameResponse:
    """Partial update of a single device. Forwards only the fields the client
    sent as a single HA `update_device` call, so one Save = one HA write."""
    payload = body.model_dump(exclude_unset=True)
    if not payload:
        raise HTTPException(status_code=400, detail="no fields to update")
    try:
        await state.ha.update_device(device_id, HADeviceUpdate.model_validate(payload))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"ha update failed: {e}") from e
    return RenameResponse(ok=True)


@router.patch("/entity/{entity_id}", response_model=RenameResponse)
async def update_entity(
    entity_id: str,
    body: UpdateEntityBody,
    state: AppState = _APP_STATE_DEPENDENCY,
) -> RenameResponse:
    """Partial update of a single entity.

    Forwards only the fields the client sent as one `update_entity` call,
    so one Save = one HA write. HA error → 502 with the HA message.
    """
    payload = body.model_dump(exclude_unset=True)
    if not payload:
        raise HTTPException(status_code=400, detail="no fields to update")
    try:
        await state.ha.update_entity(entity_id, HAEntityUpdate.model_validate(payload))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"ha update failed: {e}") from e
    return RenameResponse(ok=True)


@router.post(
    "/assign-room-entities",
    response_model=AssignRoomEntityResponse,
    response_model_exclude_none=True,
)
async def assign_room_entities(
    body: AssignRoomEntitiesBody,
    state: AppState = _APP_STATE_DEPENDENCY,
) -> AssignRoomEntityResponse:
    """Bulk-assign an area_id to one or more entities."""
    results: list[AssignRoomEntityResult] = []
    for eid in body.entity_ids:
        try:
            await state.ha.update_entity(eid, HAEntityUpdate(area_id=body.area_id))
            results.append(AssignRoomEntityResult(entity_id=eid, ok=True))
        except Exception as e:
            results.append(AssignRoomEntityResult(entity_id=eid, ok=False, error=str(e)))
    return AssignRoomEntityResponse(results=results)


@router.post(
    "/rename-pattern-entities",
    response_model=RenamePatternEntityResponse,
    response_model_exclude_none=False,
)
async def rename_pattern_entities(
    body: RenamePatternEntitiesBody,
    state: AppState = _APP_STATE_DEPENDENCY,
) -> RenamePatternEntityResponse:
    """Dual-regex rename across entity_id and / or friendly name.

    Each side is independently optional. A pattern-validation error
    returns at the top-level (short-circuits `results`). Per-entity
    HA collisions come back per row with `ok=false`.
    """
    id_pat = None
    name_pat = None
    if body.id_pattern is not None:
        try:
            id_pat = re.compile(body.id_pattern)
        except re.error as e:
            return RenamePatternEntityResponse(
                results=[], error=f"invalid id_pattern: {e}",
            )
    if body.name_pattern is not None:
        try:
            name_pat = re.compile(body.name_pattern)
        except re.error as e:
            return RenamePatternEntityResponse(
                results=[], error=f"invalid name_pattern: {e}",
            )
    if id_pat is None and name_pat is None:
        return RenamePatternEntityResponse(
            results=[], error="provide at least one of id_pattern or name_pattern",
        )

    results: list[RenamePatternEntityResult] = []
    for eid in body.entity_ids:
        e = state.entity_cache.entity(eid)
        if e is None:
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
            current = e.display_name
            proposed_name = name_pat.sub(body.name_replacement, current)
            if proposed_name != current:
                new_name = proposed_name
                name_changed = True

        if not (id_changed or name_changed):
            # Entity matched the selection but neither regex touched it.
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
    "/entity-state",
    response_model=EntityStateResponse,
    response_model_exclude_none=True,
)
async def entity_state(
    body: EntityStateBody,
    state: AppState = _APP_STATE_DEPENDENCY,
) -> EntityStateResponse:
    """Bulk flip `disabled_by` / `hidden_by` to `"user"` or `None`.

    Per-entity HA refusal (e.g. re-enabling an integration-disabled
    entity) surfaces in the per-row `error`.
    """
    if not body.entity_ids:
        raise HTTPException(status_code=400, detail="entity_ids must not be empty")
    results: list[EntityStateResult] = []
    for eid in body.entity_ids:
        try:
            await state.ha.update_entity(eid, HAEntityUpdate(**{body.field: body.value}))
            results.append(EntityStateResult(entity_id=eid, ok=True))
        except Exception as e:
            results.append(EntityStateResult(entity_id=eid, ok=False, error=str(e)))
    return EntityStateResponse(results=results)


@router.post("/delete", response_model=DeleteResponse, response_model_exclude_none=True)
async def delete(body: DeleteBody, state: AppState = _APP_STATE_DEPENDENCY) -> DeleteResponse:
    """Delete one or more devices via HA's remove_config_entry path.

    Returns per-device results so the UI can report partial success.
    """
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
    "/delete-entity",
    response_model=DeleteEntityResponse,
    response_model_exclude_none=True,
)
async def delete_entity(
    body: DeleteEntityBody,
    state: AppState = _APP_STATE_DEPENDENCY,
) -> DeleteEntityResponse:
    """Delete one or more entities via HA's entity_registry/remove.

    Mirrors the landed device `/delete` shape: cache check first, then HA
    call. Per-entity results so the UI can report partial success.
    """
    if not body.entity_ids:
        raise HTTPException(status_code=400, detail="entity_ids must not be empty")
    results: list[DeleteEntityResult] = []
    for eid in body.entity_ids:
        if state.entity_cache.entity(eid) is None:
            results.append(
                DeleteEntityResult(entity_id=eid, ok=False, error="entity not found"),
            )
            continue
        try:
            await state.ha.delete_entity(eid)
            results.append(DeleteEntityResult(entity_id=eid, ok=True))
        except Exception as e:
            results.append(DeleteEntityResult(entity_id=eid, ok=False, error=str(e)))
    return DeleteEntityResponse(results=results)
