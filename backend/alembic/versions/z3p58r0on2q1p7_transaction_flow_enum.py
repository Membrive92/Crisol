"""PHASE-34.1 — `transactions.flow` enum (IN / OUT / TRANSFER_IN / TRANSFER_OUT).

ADR-0004: la verdad del dinero pasa a vivir en la transacción. Esta fase
es PURAMENTE ADITIVA — añade la columna y la rellena por backfill, pero
NINGUNA query la lee todavía (eso es 34.2). El comportamiento no cambia.

Backfill (deriva el `flow` de la interpretación actual basada en
categoría, para que los golden tests de 34.2 prueben la EQUIVALENCIA
saldo/cashflow viejo↔nuevo):

- `is_transfer = TRUE`  + `kind = INCOME`  → `TRANSFER_IN`
- `is_transfer = TRUE`  + `kind = EXPENSE` → `TRANSFER_OUT`
- `is_transfer = FALSE` + `kind = INCOME`  → `IN`
- `is_transfer = FALSE` + `kind = EXPENSE` → `OUT`
- sin categoría (`category_id IS NULL`)    → `NULL` (neutro, contribuye 0)

NOTA: el backfill REPRODUCE los datos actuales tal cual, incluidos los
bugs medidos (transferencias en categoría de gasto, dirección invertida).
No los corrige a propósito: la corrección llega al reimportar con 34.3
(el signo del extracto manda). La columna queda NULLABLE: `NULL` = sin
clasificar, semántica idéntica al `else_=0` previo.

Idempotente: re-aplicar no pisa flows ya asignados (`WHERE flow IS NULL`).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "z3p58r0on2q1p7"
down_revision: str | None = "y2o47q9nm1p0o6"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Crear enum (idempotente).
    bind.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'transactionflow') THEN
                CREATE TYPE transactionflow AS ENUM (
                    'IN', 'OUT', 'TRANSFER_IN', 'TRANSFER_OUT'
                );
            END IF;
        END $$;
    """))

    # 2. Añadir columna NULLABLE (sin default — `NULL` = sin clasificar).
    bind.execute(sa.text("""
        ALTER TABLE transactions
        ADD COLUMN IF NOT EXISTS flow transactionflow;
    """))

    # 3. Backfill desde la categoría (equivalencia con el modelo actual).
    #    Solo toca filas sin flow; las tx sin categoría quedan en NULL.
    #    `kind` es NOT NULL en categories, así que toda fila categorizada
    #    cae en una de las cuatro ramas.
    bind.execute(sa.text("""
        UPDATE transactions t SET flow = (
            CASE
                WHEN c.is_transfer = TRUE  AND c.kind = 'INCOME'  THEN 'TRANSFER_IN'
                WHEN c.is_transfer = TRUE  AND c.kind = 'EXPENSE' THEN 'TRANSFER_OUT'
                WHEN COALESCE(c.is_transfer, FALSE) = FALSE AND c.kind = 'INCOME'  THEN 'IN'
                WHEN COALESCE(c.is_transfer, FALSE) = FALSE AND c.kind = 'EXPENSE' THEN 'OUT'
                ELSE NULL
            END
        )::transactionflow
        FROM categories c
        WHERE t.category_id = c.id AND t.flow IS NULL;
    """))

    # 4. Índice parcial para los agregados de cashflow/saldo que agrupan
    #    por flow sobre filas activas. Acelera 34.2 sin penalizar la
    #    papelera.
    bind.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS ix_transactions_user_flow_active
        ON transactions (user_id, flow)
        WHERE deleted_at IS NULL;
    """))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DROP INDEX IF EXISTS ix_transactions_user_flow_active;"))
    bind.execute(sa.text("ALTER TABLE transactions DROP COLUMN IF EXISTS flow;"))
    bind.execute(sa.text("DROP TYPE IF EXISTS transactionflow;"))
