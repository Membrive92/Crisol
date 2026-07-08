"""PHASE-37.3 — `transactions.is_exceptional`.

Override manual de tres estados sobre la clasificación estructural/puntual
del gasto (ADR de la fase en `internal_docs/phase-37-analysis-redesign.md`):

- `NULL`  → decide la heurística (`analytics/recurrence.py`).
- `TRUE`  → el usuario lo marcó como **puntual** (one-off).
- `FALSE` → el usuario lo marcó como **estructural** (recurrente).

Puramente aditiva y nullable: reversible sin pérdida (drop column). No
backfillea nada — todas las filas nacen en `NULL` (heurística decide),
que es exactamente el comportamiento previo (no había clasificación).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "c6s92u4rp6t5s1"
down_revision: str | None = "b5r81t3qo5s4r0"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("is_exceptional", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("transactions", "is_exceptional")
