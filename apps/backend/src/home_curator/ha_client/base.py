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
    async def update_device(self, device_id: str, changes: dict[str, Any]) -> None: ...
    async def delete_device(self, device_id: str) -> None: ...
    def subscribe(self, handler: EventHandler) -> Callable[[], None]: ...
