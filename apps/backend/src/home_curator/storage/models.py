from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import DateTime, Index, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


class Exception_(Base):
    """Per-device acknowledged violations. Class name trailing underscore avoids Python shadow."""

    __tablename__ = "exceptions"
    __table_args__ = (
        UniqueConstraint("device_id", "policy_id", name="uq_exceptions_device_policy"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str]
    policy_id: Mapped[str]
    acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    acknowledged_by: Mapped[str | None] = mapped_column(default=None)
    note: Mapped[str | None] = mapped_column(default=None)


class DeletionEvent(Base):
    __tablename__ = "deletion_events"
    __table_args__ = (Index("ix_deletion_identifiers", "identifiers_hash"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str]
    identifiers_hash: Mapped[str]
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reappeared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class EntityRole(Base):
    __tablename__ = "entity_roles"
    __table_args__ = (UniqueConstraint("device_id", "role", name="uq_entity_roles_device_role"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str]
    role: Mapped[Literal["battery", "connectivity"]]
    entity_id: Mapped[str]
