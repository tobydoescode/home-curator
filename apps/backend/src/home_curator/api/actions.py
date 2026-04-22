import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from home_curator.api.deps import AppState, app_state

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


@router.post("/assign-room")
async def assign_room(body: AssignRoomBody, state: AppState = Depends(app_state)):
    results = []
    for did in body.device_ids:
        try:
            await state.ha.update_device(did, {"area_id": body.area_id})
            results.append({"device_id": did, "ok": True})
        except Exception as e:
            results.append({"device_id": did, "ok": False, "error": str(e)})
    return {"results": results}


@router.post("/rename")
async def rename(body: RenameBody, state: AppState = Depends(app_state)):
    await state.ha.update_device(body.device_id, {"name_by_user": body.name_by_user})
    return {"ok": True}


@router.post("/rename-pattern")
async def rename_pattern(body: RenamePatternBody, state: AppState = Depends(app_state)):
    try:
        pat = re.compile(body.pattern)
    except re.error as e:
        return {"error": f"invalid regex: {e}", "results": []}
    results = []
    for did in body.device_ids:
        d = state.cache.device(did)
        if d is None:
            results.append({"device_id": did, "matched": False, "reason": "not in cache"})
            continue
        current = d.name_by_user or d.name
        new = pat.sub(body.replacement, current)
        if new == current:
            results.append({"device_id": did, "matched": False})
            continue
        if body.dry_run:
            results.append({"device_id": did, "matched": True, "new_name": new, "dry_run": True})
        else:
            try:
                await state.ha.update_device(did, {"name_by_user": new})
                results.append({"device_id": did, "matched": True, "new_name": new, "ok": True})
            except Exception as e:
                results.append({"device_id": did, "matched": True, "ok": False, "error": str(e)})
    return {"results": results}
