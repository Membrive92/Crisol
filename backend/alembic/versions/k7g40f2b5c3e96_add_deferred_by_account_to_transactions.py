"""PHASE-47.E2 — marca de aplazamiento en la transacción

El gasto de un ciclo aplazado EXISTE (tiene su categoría y su fecha) pero no ha
salido de la cuenta: el banco lo financió. Esta columna apunta al pasivo que lo
aplazó y sostiene las dos lecturas con una sola marca: el resultado mensual las
excluye —no salió dinero— y el desglose por categorías las mantiene, porque el
gasto se hizo.

`ON DELETE SET NULL`: borrar el pasivo no puede llevarse la compra por delante.
Lo que se pierde es la marca, y entonces la compra vuelve a contar como salida
de caja — que es exactamente lo correcto si el aplazamiento deja de existir.

Revision ID: k7g40f2b5c3e96
Revises: j6f39e1a4b2d85
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "k7g40f2b5c3e96"
down_revision = "j6f39e1a4b2d85"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("deferred_by_account_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_transactions_deferred_by_account",
        "transactions",
        "accounts",
        ["deferred_by_account_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # Índice parcial: las marcadas son una minoría (un ciclo aplazado puntual
    # entre miles de compras) y todas las consultas preguntan por las que TIENEN
    # marca o descuentan las que no.
    op.create_index(
        "ix_transactions_deferred_by_account",
        "transactions",
        ["deferred_by_account_id"],
        unique=False,
        postgresql_where=sa.text("deferred_by_account_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_deferred_by_account", table_name="transactions")
    op.drop_constraint("fk_transactions_deferred_by_account", "transactions", type_="foreignkey")
    op.drop_column("transactions", "deferred_by_account_id")
