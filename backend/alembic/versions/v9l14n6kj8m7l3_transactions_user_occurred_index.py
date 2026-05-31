"""AUDIT-2026-05 — índice compuesto (user_id, occurred_at) parcial.

Las queries de listado, dashboard, drill-down y debt-history filtran por
`user_id` + rango sobre `occurred_at` (y `deleted_at IS NULL`). El índice
parcial existente `ix_transactions_user_id_active` sólo cubre `user_id`,
así que el motor hacía un range-scan/sort sobre `occurred_at` por cada
agregación. Este btree ascendente compuesto resuelve tanto el ORDER BY
`occurred_at DESC` (scan hacia atrás) como los `occurred_at <= X`
acumulados de debt-history sin sort adicional.

Sólo filas activas (`deleted_at IS NULL`) — mismo criterio que el resto
de índices "delgados" de la tabla.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "v9l14n6kj8m7l3"
down_revision: str | None = "u8k92m4ih7l5j1"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_transactions_user_occurred_active "
            "ON transactions (user_id, occurred_at) "
            "WHERE deleted_at IS NULL;"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DROP INDEX IF EXISTS ix_transactions_user_occurred_active;"))
