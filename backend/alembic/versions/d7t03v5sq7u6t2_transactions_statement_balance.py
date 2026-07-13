"""PHASE-39 — saldo del extracto: `transactions.statement_balance` +
`accounts.anchored_statement_balance`.

1. `transactions.statement_balance` — saldo de la cuenta según el EXTRACTO
   tras cada movimiento (columna "Saldo" del fichero importado). Decimal
   firmado, `NULL` para transacciones manuales o imports sin esa columna.
   Es informativo/auditable: NO participa en el cálculo del saldo (que
   sigue siendo `opening_balance + Σflow`), pero alimenta el auto-anclaje
   y permitirá detectar huecos (saltos en la cadena saldo±importe).

2. `accounts.anchored_statement_balance` — saldo REAL declarado en el
   último anclaje ("Cuadrar saldo" manual o auto-anclaje desde import), a
   fecha `opening_balance_date`. Permite re-derivar `opening_balance`
   cuando llega historia anterior al ancla (reimportar extractos viejos
   añade movimientos ≤ fecha ancla y movería la Σ) preservando el
   invariante `saldo(fecha_ancla) == anchored_statement_balance`.

Puramente aditiva y nullable: reversible sin pérdida (drop column). No
backfillea nada — las filas existentes quedan en `NULL` (el saldo del
extracto se rellena al reimportar: las filas duplicadas por hash lo
backfillean sin duplicar transacciones).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "d7t03v5sq7u6t2"
down_revision: str | None = "c6s92u4rp6t5s1"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("statement_balance", sa.Numeric(14, 2), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("anchored_statement_balance", sa.Numeric(14, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("accounts", "anchored_statement_balance")
    op.drop_column("transactions", "statement_balance")
