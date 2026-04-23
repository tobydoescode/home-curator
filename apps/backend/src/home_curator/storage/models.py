from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import CheckConstraint, Enum as SAEnum, Index, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from home_curator.storage.types import TZDateTime


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


class Exemption(Base):
    """Per-device or per-entity acknowledged policy exemption.

    Exactly one of device_id / entity_id is non-null per row (enforced by
    `ck_exceptions_target_exactly_one`). Uniqueness is enforced on
    `(COALESCE(device_id, ''), COALESCE(entity_id, ''), policy_id)` via
    a partial unique index created in the Alembic migration.
    """

    __tablename__ = "exceptions"
    __table_args__ = (
        CheckConstraint(
            "(device_id IS NULL) <> (entity_id IS NULL)",
            name="ck_exceptions_target_exactly_one",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str | None] = mapped_column(default=None)
    entity_id: Mapped[str | None] = mapped_column(default=None)
    policy_id: Mapped[str]
    acknowledged_at: Mapped[datetime] = mapped_column(TZDateTime(), default=_now)
    acknowledged_by: Mapped[str | None] = mapped_column(default=None)
    note: Mapped[str | None] = mapped_column(default=None)


class DeletionEvent(Base):
    """Per-target deletion/reappearance audit row.

    Devices: identified by `identifiers_hash` (SHA of HA identifiers).
    Entities: `identifiers_hash` is sha of (platform, unique_id) when
    unique_id exists, else (platform, entity_id). Exactly one of
    device_id / entity_id is non-null per row.
    """

    __tablename__ = "deletion_events"
    __table_args__ = (
        Index("ix_deletion_identifiers", "identifiers_hash"),
        Index("ix_deletion_device_id", "device_id"),
        Index("ix_deletion_entity_id", "entity_id"),
        CheckConstraint(
            "(device_id IS NULL) <> (entity_id IS NULL)",
            name="ck_deletion_target_exactly_one",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str | None] = mapped_column(default=None)
    entity_id: Mapped[str | None] = mapped_column(default=None)
    platform: Mapped[str | None] = mapped_column(default=None)
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
