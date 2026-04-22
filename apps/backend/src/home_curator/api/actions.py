import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from home_curator.api.deps import AppState, app_state
from home_curator.api.schemas import (
    AssignRoomResponse,
    AssignRoomResult,
    RenamePatternResponse,
    RenamePatternResult,
    RenameResponse,
)

router = APIRouter(prefix="/api/actions", tags=["actions"])


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


@router.post("/assign-room", response_model=AssignRoomResponse, response_model_exclude_none=True)
async def assign_room(body: AssignRoomBody, state: AppState = Depends(app_state)) -> AssignRoomResponse:
    """Assign the given `area_id` to each device."""
    results = []
    for did in body.device_ids:
        try:
            await state.ha.update_device(did, {"area_id": body.area_id})
            results.append(AssignRoomResult(device_id=did, ok=True))
        except Exception as e:
            results.append(AssignRoomResult(device_id=did, ok=False, error=str(e)))
    return AssignRoomResponse(results=results)


@router.post("/rename", response_model=RenameResponse)
async def rename(body: RenameBody, state: AppState = Depends(app_state)) -> RenameResponse:
    """Rename a single device via `name_by_user`."""
    await state.ha.update_device(body.device_id, {"name_by_user": body.name_by_user})
    return RenameResponse(ok=True)


@router.post("/rename-pattern", response_model=RenamePatternResponse)
async def rename_pattern(body: RenamePatternBody, state: AppState = Depends(app_state)) -> RenamePatternResponse:
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
            results.append(RenamePatternResult(device_id=did, matched=True, new_name=new, dry_run=True))
        else:
            try:
                await state.ha.update_device(did, {"name_by_user": new})
                results.append(RenamePatternResult(device_id=did, matched=True, new_name=new, ok=True))
            except Exception as e:
                results.append(RenamePatternResult(device_id=did, matched=True, ok=False, error=str(e)))
    return RenamePatternResponse(results=results)
