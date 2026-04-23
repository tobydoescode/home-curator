from collections.abc import Callable
from typing import Any, Protocol, TypedDict, runtime_checkable


class HADeviceDict(TypedDict, total=False):
    id: str
    name: str
    name_by_user: str | None
    manufacturer: str | None
    model: str | None
    area_id: str | None
    integration: str | None
    disabled_by: str | None
    identifiers: list[list[str]]
    config_entries: list[str]
    entities: list[dict[str, str]]
    # HA registry timestamps — ISO-8601 strings on recent HA versions.
    # Absent on older versions; downstream code must tolerate missing.
    created_at: str | None
    modified_at: str | None


class HAEntityDict(TypedDict, total=False):
    """One entity row as normalized by the HA client.

    Fields mirror the HA `entity_registry` payload. All are optional for
    forward-compat: older HA versions may omit `created_at`/`modified_at`,
    and internal entities have no `unique_id`.
    """

    entity_id: str
    name: str | None            # user-set friendly name
    original_name: str | None   # integration-default friendly name
    icon: str | None
    platform: str               # integration domain, e.g. "hue"
    device_id: str | None
    area_id: str | None
    disabled_by: str | None
    hidden_by: str | None
    unique_id: str | None       # stable deletion-tracking identity
    created_at: str | None
    modified_at: str | None


class HAAreaDict(TypedDict):
    id: str
    name: str


RegistryEvent = dict[str, Any]
# Synchronous on purpose — handlers that need async work should schedule
# their own asyncio task rather than blocking the dispatcher.
EventHandler = Callable[[RegistryEvent], None]


@runtime_checkable
class HAClient(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def get_devices(self) -> list[HADeviceDict]: ...
    async def get_areas(self) -> list[HAAreaDict]: ...
    async def get_entities(self) -> list[HAEntityDict]: ...
    async def update_device(self, device_id: str, changes: dict[str, Any]) -> None: ...
    async def delete_device(self, device_id: str) -> None: ...
    async def update_entity(self, entity_id: str, changes: dict[str, Any]) -> None: ...
    async def delete_entity(self, entity_id: str) -> None: ...
    def subscribe(self, handler: EventHandler) -> Callable[[], None]: ...
