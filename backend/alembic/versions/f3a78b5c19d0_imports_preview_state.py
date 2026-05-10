"""imports preview state — add PREVIEW status + preview_payload column

Revision ID: f3a78b5c19d0
Revises: e8c34a9b1d52
Create Date: 2026-05-07 00:00:00.000000

PHASE-18 — wizard de importación en dos pasos. El usuario sube el
fichero y ve un preview de las filas detectadas antes de confirmar.
El job se persiste en estado `preview` con las filas parseadas en
una columna JSON; el commit las convierte en transacciones.

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "f3a78b5c19d0"
down_revision: str | None = "e8c34a9b1d52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Postgres no permite ADD VALUE a un enum dentro de una transacción
    # implícita. autocommit_block lo aísla en su propia tx.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE importjobstatus ADD VALUE IF NOT EXISTS 'PREVIEW'")

    op.add_column(
        "import_jobs",
        sa.Column("preview_payload", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("import_jobs", "preview_payload")
    # No revertimos el enum value: Postgres no permite quitar valores
    # de un enum sin recrearlo, y no hay forma segura si quedan jobs
    # en estado `preview`. Es seguro dejar el value huérfano.
