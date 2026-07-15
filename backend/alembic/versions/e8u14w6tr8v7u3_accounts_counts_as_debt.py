"""PHASE-40 — `accounts.counts_as_debt`: excluir del módulo de deuda las
tarjetas de crédito que el usuario paga íntegras cada mes (revolving).

`True` por defecto (todos los pasivos existentes siguen contando como deuda).
Se pone a `False` en la tarjeta revolving del usuario: sale de deuda viva / DTI
/ composición / historia / movimientos de deuda, pero SIGUE en el patrimonio
neto (el saldo del ciclo compensa el efectivo aún no adeudado). La app no puede
inferirlo (una tarjeta puede arrastrar saldo real sin cuadro), lo declara el
usuario.

Aditiva, NOT NULL con `server_default='true'`: reversible (drop column).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "e8u14w6tr8v7u3"
down_revision: str | None = "d7t03v5sq7u6t2"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column(
            "counts_as_debt",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
    )


def downgrade() -> None:
    op.drop_column("accounts", "counts_as_debt")
