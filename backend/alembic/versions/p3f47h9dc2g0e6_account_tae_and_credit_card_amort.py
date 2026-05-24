"""accounts — TAE + credit_card amortization-ready (PHASE-24.2)

Revision ID: p3f47h9dc2g0e6
Revises: o2e36g8cb1f9d5
Create Date: 2026-05-17 12:00:00.000000

PHASE-24.2:

- Añade columna `accounts.tae` (Numeric(6,4) nullable): tasa anual
  equivalente, informativa. No afecta al cálculo del cuadro francés
  (sigue usándose `apr` como TIN), pero la regulación española exige
  declararla y queremos almacenarla para mostrarla en la UI.

- (Sin migración de datos) `credit_card` pasa a aceptar
  amortization fields (apr/term_months/start_date) en código —
  necesario para modelar "tarjetas financiadas" donde BBVA fracciona
  una compra puntual con plan fijo. La columna ya existía nullable;
  no hace falta tocarla.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "p3f47h9dc2g0e6"
down_revision: str | None = "o2e36g8cb1f9d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("tae", sa.Numeric(6, 4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("accounts", "tae")
