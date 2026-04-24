"""In-memory cache of HA devices and areas, refreshed from an HAClient."""
import asyncio
import copy
from dataclasses import dataclass, field

from home_curator.ha_client.base import HAClient
from home_curator.ha_client.models import HAArea, HADevice
from home_curator.rules.base import Device, EntitySummary


@dataclass(frozen=True)
class Area:
    id: str
    name: str


@dataclass(frozen=True)
class Diff:
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)


def _to_device(d: HADevice, area_lookup: dict[str, str]) -> Device:
    return Device(
        id=d.id,
        name=d.name or d.id,
        name_by_user=d.name_by_user,
        manufacturer=d.manufacturer,
        model=d.model,
        area_id=d.area_id,
        area_name=area_lookup.get(d.area_id or "", None),
        integration=d.integration,
        disabled_by=d.disabled_by,
        # EntitySummary is a TypedDict {id: str, domain: str}; construct
        # via the TypedDict constructor so pyright infers
        # list[EntitySummary] rather than list[dict[str, Any]].
        entities=[
            EntitySummary(id=ref.id, domain=ref.domain) for ref in d.entities
        ],
        created_at=d.created_at,
        modified_at=d.modified_at,
    )


class RegistryCache:
    def __init__(self, client: HAClient) -> None:
        self._client = client
        self._devices: dict[str, Device] = {}
        self._identifiers: dict[str, tuple[tuple[str, str], ...]] = {}
        self._areas: dict[str, Area] = {}
        # Serialise load/refresh so concurrent callers don't interleave and
        # corrupt the (areas, devices) state transition.
        self._lock = asyncio.Lock()

    def devices(self) -> list[Device]:
        return list(self._devices.values())

    def areas(self) -> list[Area]:
        return list(self._areas.values())

    def device(self, device_id: str) -> Device | None:
        return self._devices.get(device_id)

    def identifiers(self, device_id: str) -> tuple[tuple[str, str], ...] | None:
        return self._identifiers.get(device_id)

    def area_name_to_id(self) -> dict[str, str]:
        return {a.name.lower(): a.id for a in self._areas.values()}

    def area_id_to_name(self) -> dict[str, str]:
        return {a.id: a.name for a in self._areas.values()}

    async def load(self) -> None:
        async with self._lock:
            await self._load_unlocked()

    async def _load_unlocked(self) -> None:
        raw_areas: list[HAArea] = await self._client.get_areas()
        self._areas = {a.id: Area(id=a.id, name=a.name) for a in raw_areas}
        raw_devices: list[HADevice] = await self._client.get_devices()
        lookup = self.area_id_to_name()
        self._devices = {d.id: _to_device(d, lookup) for d in raw_devices}
        self._identifiers = {
            d.id: tuple((i[0], i[1]) for i in d.identifiers if len(i) >= 2)
            for d in raw_devices
        }

    async def refresh(self) -> Diff:
        async with self._lock:
            before = set(self._devices)
            # Deep-copy so a later mutation of Device.entities/state doesn't
            # corrupt the before-snapshot (Device is non-frozen).
            before_snapshot = {k: copy.deepcopy(v) for k, v in self._devices.items()}
            await self._load_unlocked()
            after = set(self._devices)
        added = sorted(after - before)
        removed = sorted(before - after)
        updated = sorted(
            did
            for did in after & before
            if before_snapshot[did] != self._devices[did]
        )
        return Diff(added=added, removed=removed, updated=updated)
