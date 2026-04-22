from collections.abc import Callable
from typing import Any

from home_curator.ha_client.base import EventHandler, HAAreaDict, HADeviceDict, RegistryEvent


class FakeHAClient:
    def __init__(
        self, devices: list[HADeviceDict], areas: list[HAAreaDict]
    ) -> None:
        self._devices = list(devices)
        self._areas = list(areas)
        self._handlers: list[EventHandler] = []
        self.update_calls: list[tuple[str, dict[str, Any]]] = []

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def get_devices(self) -> list[HADeviceDict]:
        return list(self._devices)

    async def get_areas(self) -> list[HAAreaDict]:
        return list(self._areas)

    async def update_device(self, device_id: str, changes: dict[str, Any]) -> None:
        self.update_calls.append((device_id, dict(changes)))
        for d in self._devices:
            if d["id"] == device_id:
                d.update(changes)

    def subscribe(self, handler: EventHandler) -> Callable[[], None]:
        self._handlers.append(handler)

        def unsub() -> None:
            try:
                self._handlers.remove(handler)
            except ValueError:
                pass  # already removed; idempotent

        return unsub

    # Test helpers
    async def emit(self, event: RegistryEvent) -> None:
        for h in list(self._handlers):
            h(event)

    def set_devices(self, devices: list[HADeviceDict]) -> None:
        self._devices = list(devices)

    def set_areas(self, areas: list[HAAreaDict]) -> None:
        self._areas = list(areas)
