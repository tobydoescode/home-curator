"""In-memory cache of HA entities. Mirrors RegistryCache (device cache)
but keyed by entity_id; optional area + device hydration happens inline
so rule-engine input is a single flat read."""
import asyncio
import copy
from collections.abc import Callable
from dataclasses import dataclass, field

from home_curator.ha_client.base import HAClient
from home_curator.ha_client.models import HAEntity
from home_curator.rules.base import Device, Entity


@dataclass(frozen=True)
class Diff:
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)


def _domain_of(entity_id: str) -> str:
    return entity_id.split(".", 1)[0] if "." in entity_id else ""


def _to_entity(
    e: HAEntity,
    area_lookup: dict[str, str],
    device_lookup: Callable[[str], Device | None],
) -> Entity:
    area_id = e.area_id
    device_id = e.device_id
    # Effective area (for area_name lookup only): entity's own overrides
    # device's when set.
    effective_area_id = area_id
    if effective_area_id is None and device_id is not None:
        dev = device_lookup(device_id)
        if dev is not None:
            effective_area_id = dev.area_id
    return Entity(
        entity_id=e.entity_id,
        name=e.name,
        original_name=e.original_name,
        icon=e.icon,
        domain=_domain_of(e.entity_id),
        platform=e.platform,
        device_id=device_id,
        # area_id stays as the entity's own override, NOT effective_area_id.
        area_id=area_id,
        area_name=area_lookup.get(effective_area_id or "", None),
        disabled_by=e.disabled_by,
        hidden_by=e.hidden_by,
        unique_id=e.unique_id,
        created_at=e.created_at,
        modified_at=e.modified_at,
    )


class EntityRegistryCache:
    """Entity cache. `area_lookup` and `device_lookup` are callables so the
    cache reads the latest device/area state on every load without
    a hard dependency on `RegistryCache`.
    """

    def __init__(
        self,
        client: HAClient,
        *,
        area_lookup: Callable[[], dict[str, str]],
        device_lookup: Callable[[str], Device | None],
    ) -> None:
        self._client = client
        self._area_lookup = area_lookup
        self._device_lookup = device_lookup
        self._entities: dict[str, Entity] = {}
        self._unique_id_index: dict[tuple[str, str], str] = {}
        self._lock = asyncio.Lock()

    def entities(self) -> list[Entity]:
        return list(self._entities.values())

    def entity(self, entity_id: str) -> Entity | None:
        return self._entities.get(entity_id)

    def entity_id_for_identity(self, platform: str, unique_id: str) -> str | None:
        """Reverse lookup used by the deletion tracker when a known identity
        reappears under a different entity_id."""
        return self._unique_id_index.get((platform, unique_id))

    async def load(self) -> None:
        async with self._lock:
            await self._load_unlocked()

    async def _load_unlocked(self) -> None:
        raw: list[HAEntity] = await self._client.get_entities()
        area_lookup = self._area_lookup()
        self._entities = {
            e.entity_id: _to_entity(e, area_lookup, self._device_lookup)
            for e in raw
        }
        self._unique_id_index = {
            (e.platform, e.unique_id): e.entity_id
            for e in self._entities.values()
            if e.unique_id
        }

    async def refresh(self) -> Diff:
        async with self._lock:
            before = set(self._entities)
            before_snapshot = {k: copy.deepcopy(v) for k, v in self._entities.items()}
            await self._load_unlocked()
            after = set(self._entities)
        added = sorted(after - before)
        removed = sorted(before - after)
        updated = sorted(
            eid
            for eid in after & before
            if before_snapshot[eid] != self._entities[eid]
        )
        return Diff(added=added, removed=removed, updated=updated)
