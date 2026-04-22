"""Tracks device deletions and reappearances via cache state transitions."""
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from home_curator.registry_cache.cache import RegistryCache
from home_curator.rules.reappeared_after_delete import STATE_KEY_REAPPEARED
from home_curator.storage.deletion_repo import DeletionRepo, identifiers_hash


class DeletionTracker:
    """Compares cache state transitions, records deletions and detects reappearances.

    Maintains a device_id -> state dict used by the rule engine (reappeared_after_delete).
    """

    def __init__(self, cache: RegistryCache, session: Session) -> None:
        self._cache = cache
        self._repo = DeletionRepo(session)
        self._state: dict[str, dict[str, Any]] = {}
        # Snapshot of identifiers by device id for diffing
        self._last_known_identifiers: dict[str, tuple[tuple[str, str], ...]] = {
            d.id: cache.identifiers(d.id) or () for d in cache.devices()
        }
        self._last_known_first_seen: dict[str, datetime] = {
            d.id: datetime.now(UTC) for d in cache.devices()
        }

    def state_for(self, device_id: str) -> dict[str, Any]:
        return dict(self._state.get(device_id, {}))

    def all_state(self) -> dict[str, dict[str, Any]]:
        return {k: dict(v) for k, v in self._state.items()}

    def handle_diff_from_cache(self) -> None:
        """Call after `cache.refresh()`. Diffs current vs last snapshot; updates DB + state."""
        current_ids = {d.id for d in self._cache.devices()}
        before_ids = set(self._last_known_identifiers)

        # Deletions
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

        # Additions (may be reappearances)
        for did in current_ids - before_ids:
            identifiers = self._cache.identifiers(did) or ()
            if not identifiers:
                continue
            h = identifiers_hash(identifiers)
            if self._repo.is_reappearance(h):
                self._repo.mark_reappeared(h)
                self._state[did] = {STATE_KEY_REAPPEARED: True}

        # Snapshot for next round
        self._last_known_identifiers = {
            d.id: self._cache.identifiers(d.id) or () for d in self._cache.devices()
        }
        self._last_known_first_seen.update({
            d.id: self._last_known_first_seen.get(d.id, datetime.now(UTC))
            for d in self._cache.devices()
        })
