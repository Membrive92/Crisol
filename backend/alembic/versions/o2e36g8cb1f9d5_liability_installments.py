"""liability_installments — cuotas persistidas de liabilities con backfill (PHASE-24.1)

Revision ID: o2e36g8cb1f9d5
Revises: n1d25f7ba0e8d4
Create Date: 2026-05-17 00:00:00.000000

PHASE-24.1 — el cuadro de amortización pasa de "calculado en vivo" a
"persistido y editable":

- Nueva tabla `liability_installments` con una fila por cuota
  (payment, interest, principal, remaining_balance, paid_at,
  paid_transaction_id).
- Backfill: para cada liability existente con apr+term_months+
  start_date+opening_balance>0 generamos las cuotas usando el mismo
  helper `build_schedule` que el código de producción — así no
  duplicamos el algoritmo en SQL.

Las ediciones de cuotas son overrides puntuales — no recomputan las
siguientes.
"""
from collections.abc import Sequence
from decimal import Decimal
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

from app.modules.personal_finance.accounts.amortization import build_schedule


revision: str = "o2e36g8cb1f9d5"
down_revision: str | None = "n1d25f7ba0e8d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "liability_installments",
        sa.Column("id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "account_id",
            sa.UUID(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("installment_index", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("payment", sa.Numeric(14, 2), nullable=False),
        sa.Column("interest", sa.Numeric(14, 2), nullable=False),
        sa.Column("principal", sa.Numeric(14, 2), nullable=False),
        sa.Column("remaining_balance", sa.Numeric(14, 2), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "paid_transaction_id",
            sa.UUID(),
            sa.ForeignKey("transactions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "account_id",
            "installment_index",
            name="uq_liability_installments_account_index",
        ),
    )

    # Backfill: para cada loan/mortgage existente con apr+term+start_date
    # y opening_balance>0, generamos las cuotas con `build_schedule` (mismo
    # helper que usa el endpoint de amortización pre-PHASE-24.1).
    conn = op.get_bind()
    eligible = conn.execute(
        sa.text(
            "SELECT id, user_id, opening_balance, apr, term_months, start_date "
            "FROM accounts "
            "WHERE nature = 'LIABILITY' "
            # Los enums se serializan en UPPER en Postgres (alineado en
            # PHASE-5.2 con la migración g4b89c612e07).
            "AND type IN ('LOAN', 'MORTGAGE') "
            "AND apr IS NOT NULL "
            "AND term_months IS NOT NULL "
            "AND start_date IS NOT NULL "
            "AND opening_balance > 0"
        )
    ).fetchall()

    if not eligible:
        return

    rows_to_insert: list[dict[str, object]] = []
    for row in eligible:
        schedule = build_schedule(
            principal=Decimal(row.opening_balance),
            apr=Decimal(row.apr),
            term_months=row.term_months,
            start_date=row.start_date,
        )
        for s in schedule:
            rows_to_insert.append(
                {
                    "id": uuid4(),
                    "user_id": row.user_id,
                    "account_id": row.id,
                    "installment_index": s.month,
                    "due_date": s.due_date,
                    "payment": s.payment,
                    "interest": s.interest,
                    "principal": s.principal,
                    "remaining_balance": s.remaining_balance,
                }
            )

    if rows_to_insert:
        conn.execute(
            sa.text(
                "INSERT INTO liability_installments "
                "(id, user_id, account_id, installment_index, due_date, "
                "payment, interest, principal, remaining_balance) "
                "VALUES (:id, :user_id, :account_id, :installment_index, "
                ":due_date, :payment, :interest, :principal, :remaining_balance) "
                "ON CONFLICT (account_id, installment_index) DO NOTHING"
            ),
            rows_to_insert,
        )


def downgrade() -> None:
    op.drop_table("liability_installments")
