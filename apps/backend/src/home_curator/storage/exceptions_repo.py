from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from home_curator.storage.models import Exemption


class ExceptionsRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def acknowledge(self, device_id: str, policy_id: str, note: str | None = None) -> None:
        existing = self.session.execute(
            select(Exemption).where(
                Exemption.device_id == device_id, Exemption.policy_id == policy_id
            )
        ).scalar_one_or_none()
        if existing:
            existing.note = note
            existing.acknowledged_at = datetime.now(UTC)
        else:
            self.session.add(Exemption(device_id=device_id, policy_id=policy_id, note=note))

    def clear(self, device_id: str, policy_id: str) -> None:
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
        rows = self.session.execute(select(Exemption.device_id, Exemption.policy_id)).all()
        return {(r.device_id, r.policy_id) for r in rows}
