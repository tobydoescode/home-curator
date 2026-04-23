"""Repository for policy exemptions acknowledged on devices or entities."""
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from home_curator.storage.models import Exemption

TargetKind = Literal["device", "entity"]


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
        """Device-scoped ack. Kept for backwards compatibility; forwards
        to a single shared insert/update with target_kind='device'."""
        self._upsert(
            device_id=device_id,
            entity_id=None,
            policy_id=policy_id,
            note=note,
            acknowledged_by=acknowledged_by,
        )

    def ack_entity(
        self,
        entity_id: str,
        policy_id: str,
        note: str | None = None,
        acknowledged_by: str | None = None,
    ) -> None:
        self._upsert(
            device_id=None,
            entity_id=entity_id,
            policy_id=policy_id,
            note=note,
            acknowledged_by=acknowledged_by,
        )

    def _upsert(
        self,
        *,
        device_id: str | None,
        entity_id: str | None,
        policy_id: str,
        note: str | None,
        acknowledged_by: str | None,
    ) -> None:
        if (device_id is None) == (entity_id is None):
            raise ValueError("exactly one of device_id or entity_id required")
        stmt = select(Exemption).where(Exemption.policy_id == policy_id)
        if device_id is not None:
            stmt = stmt.where(
                Exemption.device_id == device_id, Exemption.entity_id.is_(None)
            )
        else:
            stmt = stmt.where(
                Exemption.entity_id == entity_id, Exemption.device_id.is_(None)
            )
        existing = self.session.execute(stmt).scalar_one_or_none()
        if existing:
            existing.note = note
            existing.acknowledged_by = acknowledged_by
            existing.acknowledged_at = datetime.now(UTC)
        else:
            self.session.add(
                Exemption(
                    device_id=device_id,
                    entity_id=entity_id,
                    policy_id=policy_id,
                    note=note,
                    acknowledged_by=acknowledged_by,
                )
            )

    def clear(self, device_id: str, policy_id: str) -> None:
        """Delete the device exemption for (device_id, policy_id). No-op if absent."""
        self.session.execute(
            delete(Exemption).where(
                Exemption.device_id == device_id,
                Exemption.entity_id.is_(None),
                Exemption.policy_id == policy_id,
            )
        )

    def clear_entity(self, entity_id: str, policy_id: str) -> None:
        self.session.execute(
            delete(Exemption).where(
                Exemption.entity_id == entity_id,
                Exemption.device_id.is_(None),
                Exemption.policy_id == policy_id,
            )
        )

    def for_device(self, device_id: str) -> list[Exemption]:
        return list(
            self.session.execute(
                select(Exemption).where(
                    Exemption.device_id == device_id,
                    Exemption.entity_id.is_(None),
                )
            ).scalars()
        )

    def for_entity(self, entity_id: str) -> list[Exemption]:
        return list(
            self.session.execute(
                select(Exemption).where(
                    Exemption.entity_id == entity_id,
                    Exemption.device_id.is_(None),
                )
            ).scalars()
        )

    def is_acknowledged(self, device_id: str, policy_id: str) -> bool:
        return (
            self.session.execute(
                select(Exemption.id).where(
                    Exemption.device_id == device_id,
                    Exemption.entity_id.is_(None),
                    Exemption.policy_id == policy_id,
                )
            ).first()
            is not None
        )

    def all_acknowledged_keys(
        self,
    ) -> set[tuple[TargetKind, str, str]]:
        """Return every acknowledged (kind, target_id, policy_id) triple.

        `kind` discriminates between device and entity exceptions so the
        rule engine can't accidentally match a device id against an entity
        id with the same surface value.
        """
        rows = self.session.execute(
            select(Exemption.device_id, Exemption.entity_id, Exemption.policy_id)
        ).all()
        out: set[tuple[TargetKind, str, str]] = set()
        for r in rows:
            if r.device_id is not None:
                out.add(("device", r.device_id, r.policy_id))
            elif r.entity_id is not None:
                out.add(("entity", r.entity_id, r.policy_id))
        return out

    def list_all(self) -> list[Exemption]:
        """Unpaginated cross-kind list, newest first. Used by the
        extended /api/exceptions listing (Plan 3)."""
        return list(
            self.session.execute(
                select(Exemption).order_by(Exemption.acknowledged_at.desc())
            ).scalars()
        )

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
        entity_ids: set[str] | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Exemption], int]:
        """Paginated exception list, newest-first.

        Filters are ANDed. `search` matches substring against note OR
        device_id OR entity_id (case-insensitive). Passing `device_ids`
        restricts to device-kind rows; passing `entity_ids` restricts to
        entity-kind rows; passing neither returns both kinds.
        """
        stmt = select(Exemption)
        if policy_ids:
            stmt = stmt.where(Exemption.policy_id.in_(policy_ids))
        if device_ids:
            stmt = stmt.where(Exemption.device_id.in_(device_ids))
        if entity_ids:
            stmt = stmt.where(Exemption.entity_id.in_(entity_ids))
        if search:
            like = f"%{search.lower()}%"
            stmt = stmt.where(
                or_(
                    Exemption.note.is_not(None) & (Exemption.note.ilike(like)),
                    Exemption.device_id.is_not(None) & Exemption.device_id.ilike(like),
                    Exemption.entity_id.is_not(None) & Exemption.entity_id.ilike(like),
                )
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
