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
