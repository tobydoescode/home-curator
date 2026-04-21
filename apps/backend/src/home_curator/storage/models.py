from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import Enum as SAEnum, Index, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from home_curator.storage.types import TZDateTime


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


class Exemption(Base):
    """Per-device acknowledged policy exemption."""

    __tablename__ = "exceptions"
    __table_args__ = (
        UniqueConstraint("device_id", "policy_id", name="uq_exceptions_device_policy"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str]
    policy_id: Mapped[str]
    acknowledged_at: Mapped[datetime] = mapped_column(TZDateTime(), default=_now)
    acknowledged_by: Mapped[str | None] = mapped_column(default=None)
    note: Mapped[str | None] = mapped_column(default=None)


class DeletionEvent(Base):
    __tablename__ = "deletion_events"
    __table_args__ = (
        Index("ix_deletion_identifiers", "identifiers_hash"),
        Index("ix_deletion_device_id", "device_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str]
    identifiers_hash: Mapped[str]
    first_seen_at: Mapped[datetime] = mapped_column(TZDateTime())
    deleted_at: Mapped[datetime] = mapped_column(TZDateTime())
    reappeared_at: Mapped[datetime | None] = mapped_column(TZDateTime(), default=None)


class EntityRole(Base):
    __tablename__ = "entity_roles"
    __table_args__ = (UniqueConstraint("device_id", "role", name="uq_entity_roles_device_role"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str]
    role: Mapped[Literal["battery", "connectivity"]] = mapped_column(
        SAEnum("battery", "connectivity", name="entity_role_enum", create_constraint=True),
    )
    entity_id: Mapped[str]
