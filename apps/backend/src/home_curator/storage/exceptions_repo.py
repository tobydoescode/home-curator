"""Repository for policy exemptions acknowledged on devices."""
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from home_curator.storage.models import Exemption


class ExceptionsRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def acknowledge(
        self,
        device_id: str,
        policy_id: str,
        note: str | None = None,
        acknowledged_by: str | None = None,
    ) -> None:
        # Select-then-insert pattern: under concurrent writers this can race and
        # hit the uniqueness constraint. For the single-process HA addon this is
        # acceptable; if concurrency grows, switch to INSERT OR REPLACE.
        existing = self.session.execute(
            select(Exemption).where(
                Exemption.device_id == device_id, Exemption.policy_id == policy_id
            )
        ).scalar_one_or_none()
        if existing:
            existing.note = note
            existing.acknowledged_by = acknowledged_by
            existing.acknowledged_at = datetime.now(UTC)
        else:
            self.session.add(
                Exemption(
                    device_id=device_id,
                    policy_id=policy_id,
                    note=note,
                    acknowledged_by=acknowledged_by,
                )
            )

    def clear(self, device_id: str, policy_id: str) -> None:
        """Delete the exemption for (device_id, policy_id). No-op if absent."""
        self.session.execute(
            delete(Exemption).where(
                Exemption.device_id == device_id, Exemption.policy_id == policy_id
            )
        )

    def for_device(self, device_id: str) -> list[Exemption]:
        return list(
            self.session.execute(
                select(Exemption).where(Exemption.device_id == device_id)
            ).scalars()
        )

    def is_acknowledged(self, device_id: str, policy_id: str) -> bool:
        return (
            self.session.execute(
                select(Exemption.id).where(
                    Exemption.device_id == device_id, Exemption.policy_id == policy_id
                )
            ).first()
            is not None
        )

    def all_acknowledged_keys(self) -> set[tuple[str, str]]:
        """Return every acknowledged (device_id, policy_id) pair.

        Used by the rule engine to build the per-evaluation exception set.
        Loads the entire exemptions table; assumes size remains modest (one
        row per device/rule pair). Re-consider caching if this becomes hot.
        """
        rows = self.session.execute(select(Exemption.device_id, Exemption.policy_id)).all()
        return {(r.device_id, r.policy_id) for r in rows}

    def delete_not_in(self, policy_ids: set[str]) -> int:
        """Delete every exception whose policy_id is NOT in policy_ids.

        Returns the count deleted. Used for cascade-on-policy-removal.
        """
        if policy_ids:
            result = self.session.execute(
                delete(Exemption).where(Exemption.policy_id.notin_(policy_ids))
            )
        else:
            result = self.session.execute(delete(Exemption))
        return result.rowcount or 0

    def list_paginated(
        self,
        *,
        search: str | None = None,
        policy_ids: set[str] | None = None,
        device_ids: set[str] | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Exemption], int]:
        """Paginated exception list, newest-first.

        Filters are ANDed. `search` matches substring against note OR device_id
        (case-insensitive). device_name / area filtering happens in the API
        layer because the registry is out-of-process.
        """
        stmt = select(Exemption)
        if policy_ids:
            stmt = stmt.where(Exemption.policy_id.in_(policy_ids))
        if device_ids:
            stmt = stmt.where(Exemption.device_id.in_(device_ids))
        if search:
            like = f"%{search.lower()}%"
            stmt = stmt.where(
                (Exemption.note.is_not(None) & (Exemption.note.ilike(like)))
                | Exemption.device_id.ilike(like)
            )
        from sqlalchemy import func
        total = self.session.execute(
            select(func.count()).select_from(stmt.subquery())
        ).scalar_one()
        stmt = stmt.order_by(Exemption.acknowledged_at.desc()).limit(page_size).offset(
            (page - 1) * page_size
        )
        rows = list(self.session.execute(stmt).scalars())
        return rows, int(total)

    def bulk_delete(self, ids: set[int]) -> int:
        if not ids:
            return 0
        result = self.session.execute(delete(Exemption).where(Exemption.id.in_(ids)))
        return result.rowcount or 0
