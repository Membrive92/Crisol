"""PHASE-32 — `accounts.is_default` (cuenta principal por defecto).

Las transacciones / imports / tickets pre-seleccionan la cuenta marcada
como principal, de modo que ingresos y gastos iteran sobre ella sin
elegirla cada vez (su saldo refleja el ahorro neto). Única por usuario:
el service desmarca las demás al marcar una.

Columna NOT NULL con `DEFAULT FALSE` → backfill implícito a `false` en
las filas existentes; ningún usuario tiene cuenta por defecto hasta que
lo marque explícitamente (el frontend cae a la primera cuenta como
fallback).
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "w0m25o7lk9n8m4"
down_revision: str | None = "v9l14n6kj8m7l3"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "ALTER TABLE accounts "
            "ADD COLUMN IF NOT EXISTS is_default BOOLEAN NOT NULL DEFAULT FALSE;"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("ALTER TABLE accounts DROP COLUMN IF EXISTS is_default;"))
