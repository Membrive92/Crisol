"""transfers — transfer_pair_id en transactions para emparejar movimientos internos

Revision ID: k8a92c4e7d5a1
Revises: j7e95d1b3f4c
Create Date: 2026-05-10 12:00:00.000000

PHASE-19.3 — añade `transactions.transfer_pair_id` (FK auto-referente,
NULLABLE, ON DELETE SET NULL). Cuando una tx forma parte de una
transferencia interna entre dos cuentas del usuario, su `transfer_pair_id`
apunta a la otra mitad del par (y viceversa, bidireccional).

Las txs con `transfer_pair_id IS NOT NULL` se excluyen de los cómputos
de cashflow / tasa de ahorro / donut / budgets — afectan al saldo de su
cuenta pero NO al flujo neto del usuario.

Sin wipe esta vez: la columna se añade NULLABLE y todas las txs
existentes quedan en NULL (= no son transferencia, comportamiento
idéntico al de antes de PHASE-19.3).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "k8a92c4e7d5a1"
down_revision: str | None = "j7e95d1b3f4c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("transfer_pair_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_transactions_transfer_pair_id",
        "transactions",
        "transactions",
        ["transfer_pair_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # Index parcial — sólo nos interesa filtrar/JOIN sobre filas que
    # están emparejadas y activas (ni soft-deleted ni huérfanas).
    op.create_index(
        "ix_transactions_transfer_pair_id",
        "transactions",
        ["transfer_pair_id"],
        unique=False,
        postgresql_where=sa.text(
            "transfer_pair_id IS NOT NULL AND deleted_at IS NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_transactions_transfer_pair_id", table_name="transactions"
    )
    op.drop_constraint(
        "fk_transactions_transfer_pair_id",
        "transactions",
        type_="foreignkey",
    )
    op.drop_column("transactions", "transfer_pair_id")
