import hashlib
from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import select, update
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
        identifiers_hash: str,
        first_seen_at: datetime,
        deleted_at: datetime,
    ) -> None:
        self.session.add(
            DeletionEvent(
                device_id=device_id,
                identifiers_hash=identifiers_hash,
                first_seen_at=first_seen_at,
                deleted_at=deleted_at,
            )
        )

    def is_reappearance(self, identifiers_hash: str) -> bool:
        return (
            self.session.execute(
                select(DeletionEvent.id).where(
                    DeletionEvent.identifiers_hash == identifiers_hash,
                )
            ).first()
            is not None
        )

    def mark_reappeared(self, identifiers_hash: str) -> None:
        self.session.execute(
            update(DeletionEvent)
            .where(
                DeletionEvent.identifiers_hash == identifiers_hash,
                DeletionEvent.reappeared_at.is_(None),
            )
            .values(reappeared_at=datetime.now(UTC))
        )

    def events_for_hash(self, identifiers_hash: str) -> list[DeletionEvent]:
        return list(
            self.session.execute(
                select(DeletionEvent).where(
                    DeletionEvent.identifiers_hash == identifiers_hash
                )
            ).scalars()
        )

    def all_reappeared_hashes(self) -> set[str]:
        rows = self.session.execute(
            select(DeletionEvent.identifiers_hash).where(
                DeletionEvent.reappeared_at.isnot(None)
            )
        ).all()
        return {r[0] for r in rows}
