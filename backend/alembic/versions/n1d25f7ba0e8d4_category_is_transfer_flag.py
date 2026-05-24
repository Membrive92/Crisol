"""categories — add `is_transfer` flag + revert kind=TRANSFER to original sign (PHASE-23.1)

Revision ID: n1d25f7ba0e8d4
Revises: m0c14e6a9f7c3
Create Date: 2026-05-15 22:00:00.000000

PHASE-23.1 corrige el acoplamiento que PHASE-23 introdujo entre dos
responsabilidades distintas:
- `kind` decide el SIGNO con que una tx afecta al saldo de su cuenta
  (asset+expense → -amount, asset+income → +amount).
- "Es transferencia interna" debería SOLO excluir del cashflow agregado
  (dashboard, presupuestos), sin tocar el signo del balance.

Al meter `TRANSFER` como tercer kind se rompió el balance: las txs
con kind=TRANSFER caían al `else_` del case (positivo siempre),
inflando saldos. Esta migración:

1. Añade `categories.is_transfer BOOLEAN DEFAULT FALSE`.
2. Para cada categoría con `kind=TRANSFER`, restaura el kind original
   (EXPENSE / INCOME) inferido por nombre, y marca `is_transfer=true`.
3. Quedan dos casos cubiertos por el seed (`Transferencias` y
   `Transferencia a favor`). Resto → fallback a EXPENSE por ser el
   caso más común de "transferencia saliente".

El value `TRANSFER` permanece en el enum categorykind (Postgres no
soporta DROP VALUE) pero el código deja de usarlo.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "n1d25f7ba0e8d4"
down_revision: str | None = "m0c14e6a9f7c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Nueva columna is_transfer
    op.add_column(
        "categories",
        sa.Column(
            "is_transfer",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # 2. Migrar categorías kind=TRANSFER a kind original + is_transfer=true.
    # Inferencia por nombre (case-insensitive):
    # - Contiene "favor" o "recibida" o "entrada" → INCOME (entrante).
    # - Resto → EXPENSE (saliente, caso más común de "Transferencias").
    op.execute(
        "UPDATE categories "
        "SET kind = 'INCOME'::categorykind, is_transfer = true "
        "WHERE kind = 'TRANSFER'::categorykind "
        "AND (name ILIKE '%favor%' OR name ILIKE '%recibida%' OR name ILIKE '%entrada%')"
    )
    op.execute(
        "UPDATE categories "
        "SET kind = 'EXPENSE'::categorykind, is_transfer = true "
        "WHERE kind = 'TRANSFER'::categorykind"
    )


def downgrade() -> None:
    # Revierte el flag a kind=TRANSFER (heurística inversa: cualquier
    # is_transfer=true vuelve al kind=TRANSFER del enum legacy). Los
    # callers que dependan de la columna fallarán hasta que se haga
    # downgrade aplicación + DB juntos.
    op.execute(
        "UPDATE categories "
        "SET kind = 'TRANSFER'::categorykind "
        "WHERE is_transfer = true"
    )
    op.drop_column("categories", "is_transfer")
