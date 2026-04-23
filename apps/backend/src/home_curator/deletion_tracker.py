"""Tracks device and entity deletions and reappearances via cache state transitions."""
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from home_curator.registry_cache.cache import RegistryCache
from home_curator.registry_cache.entity_cache import EntityRegistryCache
from home_curator.rules.reappeared_after_delete import STATE_KEY_REAPPEARED
from home_curator.storage.deletion_repo import DeletionRepo, identifiers_hash


def _entity_identity(
    platform: str, unique_id: str | None, entity_id: str
) -> tuple[str, str]:
    """Stable identity pair used to hash an entity for reappearance tracking.

    Prefer (platform, unique_id) when unique_id is present — an entity_id
    can be user-renamed, so using it as identity would miss reappearances.
    Fall back to (platform, entity_id) for entities that have no unique_id
    (some built-ins): identity is less robust but still useful.
    """
    if unique_id:
        return (platform, unique_id)
    return (platform, entity_id)


class DeletionTracker:
    """Compares cache state transitions, records deletions and detects reappearances.

    Maintains device-id → state and entity-id → state dicts used by the
    rule engine (`reappeared_after_delete`).
    """

    def __init__(
        self,
        cache: RegistryCache,
        session: Session,
        entity_cache: EntityRegistryCache | None = None,
    ) -> None:
        self._cache = cache
        self._entity_cache = entity_cache
        self._session = session
        self._repo = DeletionRepo(session)
        self._state: dict[str, dict[str, Any]] = {}
        self._entity_state: dict[str, dict[str, Any]] = {}

        self._last_known_identifiers: dict[str, tuple[tuple[str, str], ...]] = {
            d.id: cache.identifiers(d.id) or () for d in cache.devices()
        }
        self._last_known_first_seen: dict[str, datetime] = {
            d.id: datetime.now(UTC) for d in cache.devices()
        }

        # Entity snapshots keyed by entity_id.
        self._last_known_entity_identity: dict[str, tuple[str, str]] = {}
        self._last_known_entity_first_seen: dict[str, datetime] = {}
        if entity_cache is not None:
            for e in entity_cache.entities():
                self._last_known_entity_identity[e.entity_id] = _entity_identity(
                    e.platform, e.unique_id, e.entity_id
                )
                self._last_known_entity_first_seen[e.entity_id] = datetime.now(UTC)

    def commit(self) -> None:
        self._session.commit()

    # ---- device API (unchanged) ----
    def state_for(self, device_id: str) -> dict[str, Any]:
        return dict(self._state.get(device_id, {}))

    def all_state(self) -> dict[str, dict[str, Any]]:
        return {k: dict(v) for k, v in self._state.items()}

    def handle_diff_from_cache(self) -> None:
        """Device-cache diff. Call after `RegistryCache.refresh()`."""
        current_ids = {d.id for d in self._cache.devices()}
        before_ids = set(self._last_known_identifiers)

        for did in before_ids - current_ids:
            identifiers = self._last_known_identifiers[did]
            if not identifiers:
                continue
            h = identifiers_hash(identifiers)
            self._repo.record_deletion(
                device_id=did,
                id_hash=h,
                first_seen_at=self._last_known_first_seen.get(did, datetime.now(UTC)),
                deleted_at=datetime.now(UTC),
            )

        for did in current_ids - before_ids:
            identifiers = self._cache.identifiers(did) or ()
            if not identifiers:
                continue
            h = identifiers_hash(identifiers)
            if self._repo.is_reappearance(h):
                self._repo.mark_reappeared(h)
                self._state[did] = {STATE_KEY_REAPPEARED: True}

        self._last_known_identifiers = {
            d.id: self._cache.identifiers(d.id) or () for d in self._cache.devices()
        }
        self._last_known_first_seen = {
            d.id: self._last_known_first_seen.get(d.id, datetime.now(UTC))
            for d in self._cache.devices()
        }
        self._state = {
            did: s for did, s in self._state.items() if did in current_ids
        }

    # ---- entity API (new) ----
    def entity_state_for(self, entity_id: str) -> dict[str, Any]:
        return dict(self._entity_state.get(entity_id, {}))

    def all_entity_state(self) -> dict[str, dict[str, Any]]:
        return {k: dict(v) for k, v in self._entity_state.items()}

    def handle_entity_diff_from_cache(self) -> None:
        """Entity-cache diff. Call after `EntityRegistryCache.refresh()`.
        No-op if no entity_cache was provided at construction."""
        if self._entity_cache is None:
            return
        current_by_id = {e.entity_id: e for e in self._entity_cache.entities()}
        current_ids = set(current_by_id)
        before_ids = set(self._last_known_entity_identity)

        # Deletions — one row per disappeared entity_id.
        for eid in before_ids - current_ids:
            identity = self._last_known_entity_identity[eid]
            h = identifiers_hash([identity])
            platform = identity[0]
            self._repo.record_entity_deletion(
                entity_id=eid,
                platform=platform,
                id_hash=h,
                first_seen_at=self._last_known_entity_first_seen.get(
                    eid, datetime.now(UTC)
                ),
                deleted_at=datetime.now(UTC),
            )

        # Additions — may be reappearances (same identity hash under same or
        # different entity_id).
        for eid in current_ids - before_ids:
            e = current_by_id[eid]
            identity = _entity_identity(e.platform, e.unique_id, e.entity_id)
            h = identifiers_hash([identity])
            if self._repo.is_reappearance(h):
                self._repo.mark_reappeared(h)
                self._entity_state[eid] = {STATE_KEY_REAPPEARED: True}

        # Snapshot for next round, pruned to current entities.
        self._last_known_entity_identity = {
            e.entity_id: _entity_identity(e.platform, e.unique_id, e.entity_id)
            for e in self._entity_cache.entities()
        }
        self._last_known_entity_first_seen = {
            e.entity_id: self._last_known_entity_first_seen.get(
                e.entity_id, datetime.now(UTC)
            )
            for e in self._entity_cache.entities()
        }
        self._entity_state = {
            eid: s for eid, s in self._entity_state.items() if eid in current_ids
        }
