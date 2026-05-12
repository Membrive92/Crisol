"""accounts — APR + term_months + start_date para cuadro de amortización (PHASE-22)

Revision ID: l9b03d5f8e6b2
Revises: k8a92c4e7d5a1
Create Date: 2026-05-12 00:00:00.000000

PHASE-22.3 — campos opcionales en `accounts` para que las liabilities
tipo `loan` / `mortgage` puedan llevar cuadro de amortización francés:
- `apr` (NUMERIC(6,4)): tasa anual como decimal (0.0350 = 3.50%).
- `term_months` (INTEGER): plazo total en meses.
- `start_date` (DATE): inicio del préstamo.

Todos NULL en accounts existentes — no afecta a assets ni a tarjetas.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "l9b03d5f8e6b2"
down_revision: str | None = "k8a92c4e7d5a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("apr", sa.Numeric(precision=6, scale=4), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("term_months", sa.Integer(), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("start_date", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("accounts", "start_date")
    op.drop_column("accounts", "term_months")
    op.drop_column("accounts", "apr")
