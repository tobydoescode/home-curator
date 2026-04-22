"""In-memory cache of HA devices and areas, refreshed from an HAClient."""
import asyncio
import copy
from dataclasses import dataclass, field

from home_curator.ha_client.base import HAAreaDict, HAClient, HADeviceDict
from home_curator.rules.base import Device


@dataclass(frozen=True)
class Area:
    id: str
    name: str


@dataclass(frozen=True)
class Diff:
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)


def _to_device(d: HADeviceDict, area_lookup: dict[str, str]) -> Device:
    return Device(
        id=d["id"],
        name=d.get("name") or d["id"],
        name_by_user=d.get("name_by_user"),
        manufacturer=d.get("manufacturer"),
        model=d.get("model"),
        area_id=d.get("area_id"),
        area_name=area_lookup.get(d.get("area_id") or "", None),
        integration=d.get("integration"),
        disabled_by=d.get("disabled_by"),
        entities=list(d.get("entities", [])),
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
        raw_areas: list[HAAreaDict] = await self._client.get_areas()
        self._areas = {a["id"]: Area(id=a["id"], name=a["name"]) for a in raw_areas}
        raw_devices = await self._client.get_devices()
        lookup = self.area_id_to_name()
        self._devices = {d["id"]: _to_device(d, lookup) for d in raw_devices}
        self._identifiers = {
            d["id"]: tuple((i[0], i[1]) for i in d.get("identifiers", []))
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
