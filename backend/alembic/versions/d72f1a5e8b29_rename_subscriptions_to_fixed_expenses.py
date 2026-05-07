"""rename subscriptions module → fixed_expenses

Revision ID: d72f1a5e8b29
Revises: c54e9b3a7d18
Create Date: 2026-05-07 00:00:00.000000

PHASE-17.1 — el área antes llamada "subscriptions" ahora cubre
todos los gastos fijos mensuales (suscripciones, hipotecas,
préstamos, gym, etc.). Renombramos tabla y enum sin cambiar
estructura ni datos.

"""
from collections.abc import Sequence

from alembic import op


revision: str = "d72f1a5e8b29"
down_revision: str | None = "c54e9b3a7d18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Rename tabla y todos sus índices/constraints derivados
    # (Postgres mantiene los nombres de los índices con el patrón
    # `<nuevo_table>_<col>_idx`/`pk_<table>` automáticamente cuando
    # se renombran con `RENAME TO`).
    op.rename_table("subscriptions", "fixed_expenses")

    # Rename los índices manuales con prefijo de la tabla anterior.
    op.execute("ALTER INDEX ix_subscriptions_user_id RENAME TO ix_fixed_expenses_user_id")
    op.execute("ALTER INDEX ix_subscriptions_merchant RENAME TO ix_fixed_expenses_merchant")
    op.execute("ALTER INDEX ix_subscriptions_status RENAME TO ix_fixed_expenses_status")

    # Rename el tipo enum.
    op.execute("ALTER TYPE subscriptionstatus RENAME TO fixedexpensestatus")


def downgrade() -> None:
    op.execute("ALTER TYPE fixedexpensestatus RENAME TO subscriptionstatus")
    op.execute("ALTER INDEX ix_fixed_expenses_status RENAME TO ix_subscriptions_status")
    op.execute("ALTER INDEX ix_fixed_expenses_merchant RENAME TO ix_subscriptions_merchant")
    op.execute("ALTER INDEX ix_fixed_expenses_user_id RENAME TO ix_subscriptions_user_id")
    op.rename_table("fixed_expenses", "subscriptions")
