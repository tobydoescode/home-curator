from collections.abc import Callable
from typing import Any

from home_curator.ha_client.base import (
    EventHandler,
    HAAreaDict,
    HADeviceDict,
    HAEntityDict,
    RegistryEvent,
)


class FakeHAClient:
    def __init__(
        self,
        devices: list[HADeviceDict],
        areas: list[HAAreaDict],
        entities: list[HAEntityDict] | None = None,
    ) -> None:
        self._devices = list(devices)
        self._areas = list(areas)
        self._entities: list[HAEntityDict] = list(entities or [])
        self._handlers: list[EventHandler] = []
        self.update_calls: list[tuple[str, dict[str, Any]]] = []
        self.delete_calls: list[str] = []
        self.update_entity_calls: list[tuple[str, dict[str, Any]]] = []
        self.delete_entity_calls: list[str] = []

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def get_devices(self) -> list[HADeviceDict]:
        return list(self._devices)

    async def get_areas(self) -> list[HAAreaDict]:
        return list(self._areas)

    async def get_entities(self) -> list[HAEntityDict]:
        return list(self._entities)

    async def update_device(self, device_id: str, changes: dict[str, Any]) -> None:
        self.update_calls.append((device_id, dict(changes)))
        for d in self._devices:
            if d["id"] == device_id:
                # Test helper — `changes` is an arbitrary subset of HADeviceDict
                # coming from the action endpoint. TypedDict's .update() wants a
                # Partial[HADeviceDict]; the structural check here is enforced
                # by the action-layer schema, not the fake.
                d.update(changes)  # type: ignore[typeddict-item]

    async def delete_device(self, device_id: str) -> None:
        self.delete_calls.append(device_id)
        self._devices = [d for d in self._devices if d["id"] != device_id]

    async def update_entity(self, entity_id: str, changes: dict[str, Any]) -> None:
        self.update_entity_calls.append((entity_id, dict(changes)))
        for e in self._entities:
            if e["entity_id"] == entity_id:
                # See update_device for the .update() type-ignore rationale.
                e.update(changes)  # type: ignore[typeddict-item]

    async def delete_entity(self, entity_id: str) -> None:
        self.delete_entity_calls.append(entity_id)
        self._entities = [e for e in self._entities if e["entity_id"] != entity_id]

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

    def set_entities(self, entities: list[HAEntityDict]) -> None:
        self._entities = list(entities)
