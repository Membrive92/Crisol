"""transactions: qué transacción amortizó esta deuda

Aditiva y reversible: una self-FK nullable + un índice parcial.

Cuando el usuario declara que un movimiento de su banco amortiza una deuda SIN
cuadro (una tarjeta con saldo arrastrado), la deuda sólo puede bajar creando el
movimiento contrario en la cuenta de deuda. Ese movimiento necesita saber de
quién es contrapartida, y no puede decirlo `transfer_pair_id`: emparejar excluye
la pata del banco de presupuestos y de las queries de gasto del módulo de deuda
(`budgets/repository.py`, `debt/repository.py` filtran `transfer_pair_id IS
NULL`), justo lo contrario de «cuenta como gasto».

Con esta columna, la operación es detectable (¿ya está registrada?), idempotente
(409 en el segundo intento) y reversible (el `DELETE` encuentra la pata que
creó). NULL significa «este movimiento no es la contrapartida de nadie», que es
lo que le pasa al 99,9 % de las filas — no un valor por defecto que afirme algo.

Sin backfill: no hay forma de reconstruir la declaración del usuario a
posteriori, y adivinarla por importe+fecha inventaría un dato.

Revision ID: h4d17c9e2f0b63
Revises: g3c95b7d2e8f41
Create Date: 2026-08-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "h4d17c9e2f0b63"
down_revision: str | None = "g3c95b7d2e8f41"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("amortization_source_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_transactions_amortization_source_id",
        "transactions",
        "transactions",
        ["amortization_source_id"],
        ["id"],
        ondelete="CASCADE",
    )
    # Parcial: sólo las contrapartidas de una amortización llevan valor, así que
    # indexar las NULL sería indexar la tabla entera para nada.
    op.create_index(
        "ix_transactions_amortization_source",
        "transactions",
        ["amortization_source_id"],
        unique=False,
        postgresql_where=sa.text("amortization_source_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_amortization_source", table_name="transactions")
    op.drop_constraint(
        "fk_transactions_amortization_source_id", "transactions", type_="foreignkey"
    )
    op.drop_column("transactions", "amortization_source_id")
