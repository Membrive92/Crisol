"""PHASE-43.2 — `categories.expense_nature` enum (AUTO / STRUCTURAL / EXCEPTIONAL).

Override manual de la naturaleza estructural/puntual de una categoría, por
encima de la heurística de recurrencia (segundo nivel de la cascada de
precedencia de ADR-0006: tx.is_exceptional > categories.expense_nature >
heurística).

Puramente aditiva: todas las filas existentes arrancan en `AUTO` (=
comportamiento previo a la fase, decide la heurística). Sin backfill,
reversible sin pérdida (drop column + drop type).

Los labels del enum Postgres son los NOMBRES en mayúsculas del `StrEnum`
(`AUTO`/`STRUCTURAL`/`EXCEPTIONAL`), no los valores lowercase — SQLAlchemy
persiste `.name`, igual que `categorykind`/`categoryrole`. La API serializa
el value lowercase vía Pydantic.

Idempotente: `IF NOT EXISTS` en el tipo y la columna permiten re-aplicar.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "f9v25x7us9w8v4"
down_revision: str | None = "e8u14w6tr8v7u3"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'expensenature') THEN
                    CREATE TYPE expensenature AS ENUM (
                        'AUTO', 'STRUCTURAL', 'EXCEPTIONAL'
                    );
                END IF;
            END $$;
            """
        )
    )
    bind.execute(
        sa.text(
            """
            ALTER TABLE categories
            ADD COLUMN IF NOT EXISTS expense_nature expensenature
            NOT NULL DEFAULT 'AUTO';
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("ALTER TABLE categories DROP COLUMN IF EXISTS expense_nature;"))
    bind.execute(sa.text("DROP TYPE IF EXISTS expensenature;"))
