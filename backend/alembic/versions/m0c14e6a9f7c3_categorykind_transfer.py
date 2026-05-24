"""categorykind — add TRANSFER value + seed existing transfer-named categories (PHASE-23)

Revision ID: m0c14e6a9f7c3
Revises: l9b03d5f8e6b2
Create Date: 2026-05-15 00:00:00.000000

PHASE-23 — añade un tercer kind a las categorías para representar
movimientos internos entre cuentas del usuario que no son cashflow real
(no existen como pareja porque sólo se importó una pata).

Estrategia:
1. `ALTER TYPE categorykind ADD VALUE 'TRANSFER'` (autocommit_block,
   no se puede usar en la misma tx en la que se añade).
2. UPDATE de las categorías cuyo nombre matchee `(?i)transfer` para
   que pasen a kind='TRANSFER'. Cubre el caso típico ("Transferencias",
   "Transferencia a favor", "Transferencia interna", etc.) sin tocar
   categorías legítimas de income/expense.

Las queries de exclusión (dashboard, budgets) se actualizan en el
mismo commit para incluir `category.kind != 'TRANSFER'` en sus filtros.
"""
from collections.abc import Sequence

from alembic import op


revision: str = "m0c14e6a9f7c3"
down_revision: str | None = "l9b03d5f8e6b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Postgres no permite usar el value recién añadido en la misma
    # transacción — autocommit_block lo aísla en su propia tx.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE categorykind ADD VALUE IF NOT EXISTS 'TRANSFER'")

    # Seed: cualquier categoría existente cuyo nombre contenga
    # "transfer" (case-insensitive) pasa a TRANSFER. Esto cubre los
    # presets típicos sin tocar categorías como "Transferencia bancaria
    # cobrada al cliente" — patrón estricto sería contraproducente; el
    # usuario puede revertir manualmente desde la UI si discrepa.
    op.execute(
        "UPDATE categories SET kind = 'TRANSFER'::categorykind "
        "WHERE name ILIKE '%transfer%'"
    )


def downgrade() -> None:
    # Revertimos las categorías que pasaron a TRANSFER por el seed
    # — heurística: las que contienen "transfer" vuelven a EXPENSE
    # (la mayoría de "Transferencias" es una salida de dinero). El
    # usuario que tenía income las recategoriza desde la UI.
    op.execute(
        "UPDATE categories SET kind = 'EXPENSE'::categorykind "
        "WHERE kind = 'TRANSFER'::categorykind"
    )
    # Postgres no soporta DROP VALUE en enums sin recrear el tipo.
    # El value 'TRANSFER' queda huérfano pero inofensivo.
