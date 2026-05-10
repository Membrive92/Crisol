"""category_rules — rules engine para autocategorizar imports

Revision ID: i6d83e4f29a5
Revises: h5c92d703f18
Create Date: 2026-05-09 00:00:00.000000

PHASE-20 — patrones (contains/exact/starts_with/regex) sobre concepto
del banco y/o descripción para asignar categoría sin mapeo manual.
Permite el seed inicial de "categorías + reglas recomendadas para
bancos españoles".

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "i6d83e4f29a5"
down_revision: str | None = "h5c92d703f18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "category_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("pattern", sa.String(length=255), nullable=False),
        sa.Column(
            "match_type",
            sa.Enum(
                "EXACT",
                "CONTAINS",
                "STARTS_WITH",
                "REGEX",
                name="rulematchtype",
            ),
            nullable=False,
        ),
        sa.Column(
            "field",
            sa.Enum("CONCEPT", "DESCRIPTION", "BOTH", name="rulefield"),
            nullable=False,
            server_default="BOTH",  # coincide con name del Python enum
        ),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column(
            "priority", sa.Integer(), nullable=False, server_default="100"
        ),
        sa.Column(
            "enabled", sa.Boolean(), nullable=False, server_default="true"
        ),
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
        sa.ForeignKeyConstraint(
            ["category_id"], ["categories.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "pattern",
            "match_type",
            "field",
            "category_id",
            name="uq_category_rules_user_pattern",
        ),
    )
    op.create_index(
        op.f("ix_category_rules_user_id"),
        "category_rules",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_category_rules_category_id"),
        "category_rules",
        ["category_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_category_rules_category_id"), table_name="category_rules"
    )
    op.drop_index(op.f("ix_category_rules_user_id"), table_name="category_rules")
    op.drop_table("category_rules")
    sa.Enum(name="rulefield").drop(op.get_bind(), checkfirst=False)
    sa.Enum(name="rulematchtype").drop(op.get_bind(), checkfirst=False)
