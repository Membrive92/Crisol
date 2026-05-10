"""normalize enum casing — align transactionsource + fixedexpensestatus to UPPER

Revision ID: g4b89c612e07
Revises: f3a78b5c19d0
Create Date: 2026-05-08 00:00:00.000000

Alinea los enums de Postgres al casing que SQLAlchemy genera en runtime
desde `Mapped[StrEnum]` columns: el `name` del enum (UPPER), no el
`value` (lower). El módulo `imports`, `receipts` y `category` ya estaban
en UPPER. Los dos pendientes:

- `transactionsource`: existían `MANUAL`/`IMPORT`/`RECEIPT` (UPPER) pero
  PHASE-17.2 añadió `expected` (lower). El reconcile de imports
  (PHASE-17.3) filtra `source == TransactionSource.EXPECTED` que
  SQLAlchemy serializa como 'EXPECTED' → no existe → 500 al hacer commit
  de un import.

- `fixedexpensestatus`: heredado de la migración inicial de subscriptions
  (a92f5b1c8d34) que creó el enum con valores lowercase. Cualquier
  query con filtro por status (incluyendo `list_due_for_autopost`) falla
  con `invalid input value for enum`.

Estrategia: añadir los UPPER que faltan y migrar las filas existentes a
UPPER. Postgres no permite eliminar valores de un enum sin recrear el
tipo, así que los lowercase quedan huérfanos pero inofensivos.
"""
from collections.abc import Sequence

from alembic import op


revision: str = "g4b89c612e07"
down_revision: str | None = "f3a78b5c19d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # `ALTER TYPE ... ADD VALUE` no puede correr dentro de la transacción
    # implícita de Alembic (Postgres < 12 lo prohibía; en >= 12 funciona
    # pero no se puede usar el value en la misma tx). autocommit_block
    # lo aísla.
    with op.get_context().autocommit_block():
        # transactionsource: solo `expected` está en lower. Añadimos
        # `EXPECTED` para alinearlo con MANUAL/IMPORT/RECEIPT.
        op.execute("ALTER TYPE transactionsource ADD VALUE IF NOT EXISTS 'EXPECTED'")

        # fixedexpensestatus: todo en lower. Añadimos los 5 UPPER.
        op.execute("ALTER TYPE fixedexpensestatus ADD VALUE IF NOT EXISTS 'PENDING'")
        op.execute("ALTER TYPE fixedexpensestatus ADD VALUE IF NOT EXISTS 'CONFIRMED'")
        op.execute("ALTER TYPE fixedexpensestatus ADD VALUE IF NOT EXISTS 'DISMISSED'")
        op.execute("ALTER TYPE fixedexpensestatus ADD VALUE IF NOT EXISTS 'PAUSED'")
        op.execute("ALTER TYPE fixedexpensestatus ADD VALUE IF NOT EXISTS 'CANCELLED'")

    # Migrar datos existentes a UPPER. Cast doble (text → enum) porque
    # Postgres no permite UPDATE directo entre values del mismo enum.
    op.execute(
        "UPDATE transactions SET source = 'EXPECTED'::transactionsource "
        "WHERE source::text = 'expected'"
    )
    op.execute(
        "UPDATE fixed_expenses "
        "SET status = UPPER(status::text)::fixedexpensestatus"
    )


def downgrade() -> None:
    # No revertimos: los values UPPER quedan en el enum (Postgres no
    # soporta DROP VALUE), y los datos pasaron de lower a UPPER. La
    # única forma de revertir sería recrear el enum y migrar los datos
    # de vuelta — costoso y arriesgado. Si el equipo necesita rollback,
    # tocará migración manual.
    pass
