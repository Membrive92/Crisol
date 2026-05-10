"""bank_category_mappings — equivalencia concepto banco → categoría usuario

Revision ID: h5c92d703f18
Revises: g4b89c612e07
Create Date: 2026-05-08 00:00:00.000000

PHASE-19 — auto-mapeo de concepto del banco a categoría del usuario.
La primera vez que un usuario ve un concepto nuevo (p.ej. "PAGO TARJETA -
RESTAURANTES") en el preview de un import lo asigna a una categoría suya.
La equivalencia se guarda y las próximas importaciones aplican la
categoría automáticamente.

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "h5c92d703f18"
down_revision: str | None = "g4b89c612e07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bank_category_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("bank_concept", sa.String(length=255), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["category_id"], ["categories.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "bank_concept", name="uq_bank_mappings_user_concept"
        ),
    )
    op.create_index(
        op.f("ix_bank_category_mappings_user_id"),
        "bank_category_mappings",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bank_category_mappings_category_id"),
        "bank_category_mappings",
        ["category_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_bank_category_mappings_category_id"),
        table_name="bank_category_mappings",
    )
    op.drop_index(
        op.f("ix_bank_category_mappings_user_id"),
        table_name="bank_category_mappings",
    )
    op.drop_table("bank_category_mappings")
