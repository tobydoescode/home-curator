"""GET /api/areas — cached HA area registry."""
from fastapi import APIRouter, Depends

from home_curator.api.deps import AppState, app_state
from home_curator.api.schemas import AreaOut

router = APIRouter(prefix="/api", tags=["areas"])


@router.get("/areas", response_model=list[AreaOut])
def list_areas(state: AppState = Depends(app_state)) -> list[AreaOut]:
    """Return every HA area currently in the registry cache."""
    return [AreaOut(id=a.id, name=a.name) for a in state.cache.areas()]
