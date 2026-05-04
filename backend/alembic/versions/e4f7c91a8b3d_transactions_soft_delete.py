"""transactions soft delete — add deleted_at + scope import_hash dedup

Revision ID: e4f7c91a8b3d
Revises: c5d28e7f3b91
Create Date: 2026-05-04 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e4f7c91a8b3d"
down_revision: str | None = "c5d28e7f3b91"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Soft-delete column. NULL = active, timestamp = trashed at that moment.
    op.add_column(
        "transactions",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Partial index on user_id WHERE deleted_at IS NULL — covers the
    # common list/aggregate path (which all add `AND deleted_at IS NULL`)
    # without bloating the index with trashed rows.
    op.create_index(
        "ix_transactions_user_id_active",
        "transactions",
        ["user_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # The dedup unique index for imports must not block re-importing a
    # row whose previous instance was trashed. Drop and recreate the
    # partial unique with the extra `AND deleted_at IS NULL` predicate.
    op.drop_index("uq_transactions_user_import_hash", table_name="transactions")
    op.create_index(
        "uq_transactions_user_import_hash",
        "transactions",
        ["user_id", "import_hash"],
        unique=True,
        postgresql_where=sa.text("import_hash IS NOT NULL AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_transactions_user_import_hash", table_name="transactions")
    op.create_index(
        "uq_transactions_user_import_hash",
        "transactions",
        ["user_id", "import_hash"],
        unique=True,
        postgresql_where=sa.text("import_hash IS NOT NULL"),
    )
    op.drop_index("ix_transactions_user_id_active", table_name="transactions")
    op.drop_column("transactions", "deleted_at")
