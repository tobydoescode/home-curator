from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from home_curator.api.deps import AppState, app_state
from home_curator.storage.db import session_scope
from home_curator.storage.exceptions_repo import ExceptionsRepo

router = APIRouter(prefix="/api/exceptions", tags=["exceptions"])


class AcknowledgeBody(BaseModel):
    device_id: str
    policy_id: str
    note: str | None = None


@router.post("", status_code=status.HTTP_201_CREATED)
def acknowledge(body: AcknowledgeBody, state: AppState = Depends(app_state)):
    with session_scope(state.session_factory) as s:
        ExceptionsRepo(s).acknowledge(body.device_id, body.policy_id, body.note)
    return {"ok": True}


@router.delete("/{device_id}/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
def clear(device_id: str, policy_id: str, state: AppState = Depends(app_state)):
    with session_scope(state.session_factory) as s:
        ExceptionsRepo(s).clear(device_id, policy_id)
    return None


@router.get("")
def list_for_device(device_id: str, state: AppState = Depends(app_state)):
    with session_scope(state.session_factory) as s:
        rows = ExceptionsRepo(s).for_device(device_id)
        return [
            {
                "device_id": r.device_id,
                "policy_id": r.policy_id,
                "acknowledged_at": r.acknowledged_at.isoformat(),
                "note": r.note,
            }
            for r in rows
        ]
