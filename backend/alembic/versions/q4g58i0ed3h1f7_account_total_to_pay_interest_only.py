"""accounts — total_to_pay + interest_only_first_payment (PHASE-24.3)

Revision ID: q4g58i0ed3h1f7
Revises: p3f47h9dc2g0e6
Create Date: 2026-05-19 00:00:00.000000

PHASE-24.3 — Espejo del modelo de financiación que muestran los
bancos españoles (BBVA en concreto):

- `total_to_pay` (Numeric(14,2), NULL): "Total a pagar" del contrato.
  Si está informado, el cuadro de amortización deriva
  `extra_charges = total_to_pay − Σ(cuotas) − interest_only_first_payment`
  para mostrar las comisiones/cargos que el banco no desglosa pero
  sí incluye en el total (típicamente ~1-2% del capital).
- `interest_only_first_payment` (Numeric(14,2), NULL): cuota inicial
  especial que sólo paga intereses (cuando el contrato no arranca
  alineado con la fecha de cuota). 0€ en la mayoría de los casos.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "q4g58i0ed3h1f7"
down_revision: str | None = "p3f47h9dc2g0e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("total_to_pay", sa.Numeric(14, 2), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column(
            "interest_only_first_payment", sa.Numeric(14, 2), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("accounts", "interest_only_first_payment")
    op.drop_column("accounts", "total_to_pay")
