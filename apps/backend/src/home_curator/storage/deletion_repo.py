"""Repository for device deletion events and reappearance detection."""
import hashlib
from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from home_curator.storage.models import DeletionEvent


def identifiers_hash(identifiers: Iterable[tuple[str, str]]) -> str:
    """Stable hash of HA device identifiers — order-independent."""
    joined = "|".join(f"{d}:{i}" for d, i in sorted(identifiers))
    return hashlib.sha256(joined.encode()).hexdigest()[:32]


class DeletionRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record_deletion(
        self,
        device_id: str,
        id_hash: str,
        first_seen_at: datetime,
        deleted_at: datetime,
    ) -> None:
        self.session.add(
            DeletionEvent(
                device_id=device_id,
                identifiers_hash=id_hash,
                first_seen_at=first_seen_at,
                deleted_at=deleted_at,
            )
        )

    def is_reappearance(self, id_hash: str) -> bool:
        """Return True if any DeletionEvent exists for this identifiers hash.

        A device with no prior deletion is not a reappearance. A device
        deleted once, even if never yet marked as reappeared, matches here
        on its next sighting.
        """
        return (
            self.session.execute(
                select(DeletionEvent.id).where(DeletionEvent.identifiers_hash == id_hash)
            ).first()
            is not None
        )

    def mark_reappeared(self, id_hash: str) -> None:
        """Stamp `reappeared_at = now(UTC)` on every matching event still null.

        Uses ORM-level mutation (not bulk UPDATE) so the session's identity
        map stays consistent — loaded DeletionEvent instances reflect the
        new value without an explicit expire.
        """
        rows = self.session.execute(
            select(DeletionEvent).where(
                DeletionEvent.identifiers_hash == id_hash,
                DeletionEvent.reappeared_at.is_(None),
            )
        ).scalars()
        now = datetime.now(UTC)
        for row in rows:
            row.reappeared_at = now

    def events_for_hash(self, id_hash: str) -> list[DeletionEvent]:
        return list(
            self.session.execute(
                select(DeletionEvent).where(DeletionEvent.identifiers_hash == id_hash)
            ).scalars()
        )

    def all_reappeared_hashes(self) -> set[str]:
        rows = self.session.execute(
            select(DeletionEvent.identifiers_hash)
            .where(DeletionEvent.reappeared_at.isnot(None))
            .distinct()
        ).all()
        return {r[0] for r in rows}

    def record_entity_deletion(
        self,
        entity_id: str,
        platform: str | None,
        id_hash: str,
        first_seen_at: datetime,
        deleted_at: datetime,
    ) -> None:
        self.session.add(
            DeletionEvent(
                entity_id=entity_id,
                platform=platform,
                identifiers_hash=id_hash,
                first_seen_at=first_seen_at,
                deleted_at=deleted_at,
            )
        )
