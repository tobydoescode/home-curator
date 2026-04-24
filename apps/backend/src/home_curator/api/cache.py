from fastapi import APIRouter, Depends, HTTPException

from home_curator.api.deps import AppState, app_state
from home_curator.api.schemas import ResyncResponse

router = APIRouter(prefix="/api/cache", tags=["cache"])
_APP_STATE_DEPENDENCY = Depends(app_state)


@router.post("/resync", response_model=ResyncResponse)
async def resync(state: AppState = _APP_STATE_DEPENDENCY) -> ResyncResponse:
    """Force a re-pull of devices, areas and entities from Home Assistant.

    Escape hatch for when the UI looks stale. Refreshes both registry
    caches, updates the deletion tracker's in-memory state, commits its
    pending DB writes, and publishes SSE events for every cache that
    actually changed.
    """
    try:
        dev_diff = await state.cache.refresh()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"device resync failed: {e}") from e
    try:
        ent_diff = await state.entity_cache.refresh()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"entity resync failed: {e}") from e
    state.tracker.handle_diff_from_cache()
    state.tracker.handle_entity_diff_from_cache()
    state.tracker.commit()
    if dev_diff.added or dev_diff.removed or dev_diff.updated:
        await state.broker.publish({"kind": "devices_changed"})
    if ent_diff.added or ent_diff.removed or ent_diff.updated:
        await state.broker.publish({"kind": "entities_changed"})
    return ResyncResponse(
        added=len(dev_diff.added),
        removed=len(dev_diff.removed),
        updated=len(dev_diff.updated),
        entity_added=len(ent_diff.added),
        entity_removed=len(ent_diff.removed),
        entity_updated=len(ent_diff.updated),
    )
