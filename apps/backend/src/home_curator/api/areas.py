"""GET /api/areas — cached HA area registry."""
from fastapi import APIRouter, Depends

from home_curator.api.deps import AppState, app_state
from home_curator.api.schemas import AreaOut

router = APIRouter(prefix="/api", tags=["areas"])
_APP_STATE_DEPENDENCY = Depends(app_state)


@router.get("/areas", response_model=list[AreaOut])
def list_areas(state: AppState = _APP_STATE_DEPENDENCY) -> list[AreaOut]:
    """Return every HA area currently in the registry cache."""
    return [AreaOut(id=a.id, name=a.name) for a in state.cache.areas()]
