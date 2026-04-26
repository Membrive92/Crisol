"""receipts module — receipts table + transactions.receipt_id FK

Revision ID: a91d8f4c2e10
Revises: 7c3a91f4d2b8
Create Date: 2026-04-26 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a91d8f4c2e10"
down_revision: str | None = "7c3a91f4d2b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "receipts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "CONFIRMED", "REJECTED", name="receiptstatus"),
            nullable=False,
        ),
        sa.Column("blob_key", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("extraction", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("transaction_id", sa.Uuid(), nullable=True),
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
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_receipts_user_id"), "receipts", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_receipts_transaction_id"), "receipts", ["transaction_id"], unique=False
    )

    # No se añade FK desde transactions.receipt_id → receipts.id para evitar
    # ciclos. La integridad inversa (Receipt.transaction_id → transactions.id)
    # es suficiente y la lógica del service garantiza la consistencia.


def downgrade() -> None:
    op.drop_index(op.f("ix_receipts_transaction_id"), table_name="receipts")
    op.drop_index(op.f("ix_receipts_user_id"), table_name="receipts")
    op.drop_table("receipts")
    sa.Enum(name="receiptstatus").drop(op.get_bind(), checkfirst=False)
