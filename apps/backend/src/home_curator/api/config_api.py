"""GET /api/config — runtime config the frontend needs at boot."""
from fastapi import APIRouter, Depends

from home_curator.api.deps import AppState, app_state
from home_curator.api.schemas import ConfigResponse

router = APIRouter(prefix="/api", tags=["config"])
_APP_STATE_DEPENDENCY = Depends(app_state)


@router.get("/config", response_model=ConfigResponse)
def get_config(state: AppState = _APP_STATE_DEPENDENCY) -> ConfigResponse:
    """Return UI-relevant config.

    `ha_external_url` defaults to HA_EXTERNAL_URL from the environment.
    Under ingress the frontend falls back to window.location.origin, which
    resolves to the HA host. In standalone dev the env var lets the user
    point "Open in Home Assistant" at their actual HA instance.
    """
    return ConfigResponse(ha_external_url=state.settings.ha_external_url)
