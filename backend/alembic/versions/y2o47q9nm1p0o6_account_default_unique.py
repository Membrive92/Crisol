"""PHASE-32 (AUDIT LOW#11) — índice único parcial: una sola cuenta
principal por usuario a nivel de BD.

La unicidad de `is_default` la forzaba sólo el service
(`clear_default_accounts`). Un índice parcial único
`UNIQUE (user_id) WHERE is_default` la garantiza también en la BD, cerrando
la ventana de carrera (dos updates concurrentes marcando principales
distintas) y cualquier escritura directa que se salte el service.

Backfill defensivo: si por datos antiguos un usuario tuviera >1 principal,
se conserva una (orden determinista por `display_order, name, id`) y se
desmarcan las demás, para que la creación del índice no falle.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "y2o47q9nm1p0o6"
down_revision: str | None = "x1n36p8ml0o9n5"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Backfill: deja una sola principal por usuario antes de crear el índice.
    op.execute(
        "UPDATE accounts SET is_default = FALSE "
        "WHERE is_default = TRUE AND id NOT IN ("
        "  SELECT DISTINCT ON (user_id) id FROM accounts "
        "  WHERE is_default = TRUE "
        "  ORDER BY user_id, display_order, name, id"
        ")"
    )
    op.create_index(
        "uq_accounts_one_default_per_user",
        "accounts",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )


def downgrade() -> None:
    op.drop_index("uq_accounts_one_default_per_user", table_name="accounts")
