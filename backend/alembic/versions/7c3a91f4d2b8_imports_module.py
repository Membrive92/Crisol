"""imports module — import_jobs table + transactions.import_hash

Revision ID: 7c3a91f4d2b8
Revises: 4698c02a5861
Create Date: 2026-04-24 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "7c3a91f4d2b8"
down_revision: str | None = "4698c02a5861"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "import_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "PROCESSING", "COMPLETED", "FAILED", name="importjobstatus"),
            nullable=False,
        ),
        sa.Column("rows_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_ok", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("column_mappings", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("error_log", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_import_jobs_user_id"), "import_jobs", ["user_id"], unique=False)

    op.add_column(
        "transactions",
        sa.Column("import_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "uq_transactions_user_import_hash",
        "transactions",
        ["user_id", "import_hash"],
        unique=True,
        postgresql_where=sa.text("import_hash IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_transactions_user_import_hash", table_name="transactions")
    op.drop_column("transactions", "import_hash")
    op.drop_index(op.f("ix_import_jobs_user_id"), table_name="import_jobs")
    op.drop_table("import_jobs")
    sa.Enum(name="importjobstatus").drop(op.get_bind(), checkfirst=False)
