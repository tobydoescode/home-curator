from fastapi import APIRouter, Depends

from home_curator.api.deps import AppState, app_state

router = APIRouter(prefix="/api/policies", tags=["policies"])


@router.get("")
def list_policies(state: AppState = Depends(app_state)):
    if state.policies_file is None:
        return {"error": state.policies_error, "policies": []}
    errors = state.engine.compile_errors()
    return {
        "error": None,
        "policies": [
            {
                "id": p.id,
                "type": p.type,
                "enabled": p.enabled,
                "severity": p.severity,
                "compile_error": errors.get(p.id),
            }
            for p in state.policies_file.policies
        ],
    }
