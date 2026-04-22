from collections.abc import Callable
from typing import Any, Protocol, TypedDict


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
    entities: list[dict[str, str]]


class HAAreaDict(TypedDict):
    id: str
    name: str


RegistryEvent = dict[str, Any]
EventHandler = Callable[[RegistryEvent], None]


class HAClient(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def get_devices(self) -> list[HADeviceDict]: ...
    async def get_areas(self) -> list[HAAreaDict]: ...
    async def update_device(self, device_id: str, changes: dict[str, Any]) -> None: ...
    def subscribe(self, handler: EventHandler) -> Callable[[], None]: ...
