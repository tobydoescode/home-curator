"""entity_support

Widens `exceptions` and `deletion_events` to carry entity-scoped rows
alongside existing device rows. SQLite cannot drop-then-add CHECK
constraints in place; both tables are rewritten via batch_alter_table.

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-23 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- exceptions -----------------------------------------------------
    # Drop the old unique constraint before relaxing device_id nullability
    # — SQLite's batch_alter_table recreates the table anyway, but we
    # must name the constraint we're removing.
    with op.batch_alter_table("exceptions", recreate="always") as batch:
        batch.alter_column("device_id", existing_type=sa.String(), nullable=True)
        batch.add_column(sa.Column("entity_id", sa.String(), nullable=True))
        batch.drop_constraint("uq_exceptions_device_policy", type_="unique")
        batch.create_check_constraint(
            "ck_exceptions_target_exactly_one",
            "(device_id IS NULL) <> (entity_id IS NULL)",
        )

    # Unique across device-OR-entity. COALESCE lets NULL slots share a value
    # while the OR-constraint above keeps the non-null one distinct per row.
    op.execute(
        "CREATE UNIQUE INDEX ix_exceptions_target_policy "
        "ON exceptions (COALESCE(device_id, ''), COALESCE(entity_id, ''), policy_id)"
    )

    # --- deletion_events ------------------------------------------------
    with op.batch_alter_table("deletion_events", recreate="always") as batch:
        batch.alter_column("device_id", existing_type=sa.String(), nullable=True)
        batch.add_column(sa.Column("entity_id", sa.String(), nullable=True))
        batch.add_column(sa.Column("platform", sa.String(), nullable=True))
        batch.create_index("ix_deletion_entity_id", ["entity_id"], unique=False)
        batch.create_check_constraint(
            "ck_deletion_target_exactly_one",
            "(device_id IS NULL) <> (entity_id IS NULL)",
        )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_exceptions_target_policy")
    with op.batch_alter_table("exceptions", recreate="always") as batch:
        batch.drop_constraint("ck_exceptions_target_exactly_one", type_="check")
        batch.drop_column("entity_id")
        batch.alter_column("device_id", existing_type=sa.String(), nullable=False)
        batch.create_unique_constraint(
            "uq_exceptions_device_policy", ["device_id", "policy_id"]
        )

    with op.batch_alter_table("deletion_events", recreate="always") as batch:
        batch.drop_constraint("ck_deletion_target_exactly_one", type_="check")
        batch.drop_index("ix_deletion_entity_id")
        batch.drop_column("platform")
        batch.drop_column("entity_id")
        batch.alter_column("device_id", existing_type=sa.String(), nullable=False)
