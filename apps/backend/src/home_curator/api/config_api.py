"""GET /api/config — runtime config the frontend needs at boot."""
from fastapi import APIRouter

from home_curator.api.schemas import ConfigResponse
from home_curator.config import Settings

router = APIRouter(prefix="/api", tags=["config"])


@router.get("/config", response_model=ConfigResponse)
def get_config() -> ConfigResponse:
    """Return UI-relevant config.

    `ha_external_url` defaults to HA_EXTERNAL_URL from the environment.
    Under ingress the frontend falls back to window.location.origin, which
    resolves to the HA host. In standalone dev the env var lets the user
    point "Open in Home Assistant" at their actual HA instance.
    """
    s = Settings()
    return ConfigResponse(ha_external_url=s.ha_external_url)
