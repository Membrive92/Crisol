"""fixed_expenses: auto_post flag + transactionsource.expected

Revision ID: e8c34a9b1d52
Revises: d72f1a5e8b29
Create Date: 2026-05-07 00:00:00.000000

PHASE-17.2 — añade el flag opt-in `auto_post` a fixed_expenses y
extiende el enum `transactionsource` con `expected` para las
transacciones generadas por el cron de autoposteo. La
reconciliación con imports llega en PHASE-17.3.

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "e8c34a9b1d52"
down_revision: str | None = "d72f1a5e8b29"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "fixed_expenses",
        sa.Column(
            "auto_post",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    # `ALTER TYPE ... ADD VALUE` es idempotente con IF NOT EXISTS y
    # no requiere transacción especial en Postgres ≥ 12.
    op.execute("ALTER TYPE transactionsource ADD VALUE IF NOT EXISTS 'expected'")


def downgrade() -> None:
    # Postgres no soporta DROP VALUE en enums; el revert del enum
    # requeriría recrear el tipo y migrar rows. Documentado como
    # no-op consciente (mismo patrón que PHASE-15.2 con
    # subscriptionstatus). El campo `auto_post` sí se puede revertir
    # limpio.
    op.drop_column("fixed_expenses", "auto_post")
