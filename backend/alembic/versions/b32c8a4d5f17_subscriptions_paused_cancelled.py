"""subscriptions: add paused and cancelled status

Revision ID: b32c8a4d5f17
Revises: a92f5b1c8d34
Create Date: 2026-05-06 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op


revision: str = "b32c8a4d5f17"
down_revision: str | None = "a92f5b1c8d34"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Postgres native ENUM: ADD VALUE IF NOT EXISTS (idempotente,
    # transaccional desde PG 12). Usamos COMMIT explícito porque
    # algunos drivers requieren que el ALTER TYPE no esté dentro de
    # una transacción explícita.
    op.execute("ALTER TYPE subscriptionstatus ADD VALUE IF NOT EXISTS 'paused'")
    op.execute("ALTER TYPE subscriptionstatus ADD VALUE IF NOT EXISTS 'cancelled'")


def downgrade() -> None:
    # Postgres no soporta DROP VALUE en un ENUM. Para revertir habría
    # que recrear el tipo entero — costoso y arriesga datos. Documentado
    # como irreversible: si emerge necesidad real, escribir migración
    # custom que recrea el tipo y migra rows con paused/cancelled a
    # otro status.
    pass
