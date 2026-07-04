"""AUDIT-2026-07 (H-04) — `transactions.absorbed_as_mirror`.

Marca un "cargo espejo" (ADEUDO/LIQUIDACIÓN de tarjeta) que el sistema
soft-borró al absorberlo en una conversión a deuda. Distingue ese borrado
de SISTEMA del borrado de USUARIO (papelera): el dedup de imports
(`find_existing_hashes`) trata los espejos absorbidos como existentes para
que reimportar el mismo extracto no los resucite y vuelva a descuadrar el
saldo.

Puramente aditiva: columna NOT NULL con `server_default false` (rápida en
Postgres ≥ 11, sin reescritura de tabla). NULL/false = fila normal,
comportamiento previo intacto.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "b5r81t3qo5s4r0"
down_revision: str | None = "a4q70s2pn4r3q9"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column(
            "absorbed_as_mirror",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("transactions", "absorbed_as_mirror")
