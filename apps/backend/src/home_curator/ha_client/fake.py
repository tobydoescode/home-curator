from collections.abc import Callable

from home_curator.ha_client.base import EventHandler
from home_curator.ha_client.models import (
    HAArea,
    HADevice,
    HADeviceUpdate,
    HAEntity,
    HAEntityUpdate,
    HAEvent,
)


class FakeHAClient:
    def __init__(
        self,
        devices: list[HADevice],
        areas: list[HAArea],
        entities: list[HAEntity] | None = None,
    ) -> None:
        self._devices: list[HADevice] = list(devices)
        self._areas: list[HAArea] = list(areas)
        self._entities: list[HAEntity] = list(entities or [])
        self._handlers: list[EventHandler] = []
        self.update_calls: list[tuple[str, HADeviceUpdate]] = []
        self.delete_calls: list[str] = []
        self.update_entity_calls: list[tuple[str, HAEntityUpdate]] = []
        self.delete_entity_calls: list[str] = []

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def get_devices(self) -> list[HADevice]:
        return list(self._devices)

    async def get_areas(self) -> list[HAArea]:
        return list(self._areas)

    async def get_entities(self) -> list[HAEntity]:
        return list(self._entities)

    async def update_device(self, device_id: str, changes: HADeviceUpdate) -> None:
        self.update_calls.append((device_id, changes))
        patch = changes.model_dump(exclude_unset=True)
        self._devices = [
            d.model_copy(update=patch) if d.id == device_id else d
            for d in self._devices
        ]

    async def delete_device(self, device_id: str) -> None:
        self.delete_calls.append(device_id)
        self._devices = [d for d in self._devices if d.id != device_id]

    async def update_entity(self, entity_id: str, changes: HAEntityUpdate) -> None:
        self.update_entity_calls.append((entity_id, changes))
        patch = changes.model_dump(exclude_unset=True)
        # new_entity_id renames the slug; apply it by updating entity_id.
        new_id = patch.pop("new_entity_id", None)
        updated: list[HAEntity] = []
        for e in self._entities:
            if e.entity_id == entity_id:
                merged = patch.copy()
                if new_id is not None:
                    merged["entity_id"] = new_id
                updated.append(e.model_copy(update=merged))
            else:
                updated.append(e)
        self._entities = updated

    async def delete_entity(self, entity_id: str) -> None:
        self.delete_entity_calls.append(entity_id)
        self._entities = [e for e in self._entities if e.entity_id != entity_id]

    def subscribe(self, handler: EventHandler) -> Callable[[], None]:
        self._handlers.append(handler)

        def unsub() -> None:
            try:
                self._handlers.remove(handler)
            except ValueError:
                pass  # already removed; idempotent

        return unsub

    # Test helpers
    async def emit(self, event: HAEvent) -> None:
        for h in list(self._handlers):
            h(event)

    def set_devices(self, devices: list[HADevice]) -> None:
        self._devices = list(devices)

    def set_areas(self, areas: list[HAArea]) -> None:
        self._areas = list(areas)

    def set_entities(self, entities: list[HAEntity]) -> None:
        self._entities = list(entities)
