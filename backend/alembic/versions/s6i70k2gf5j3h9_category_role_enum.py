"""PHASE-30.1 — `categories.role` enum (GENERIC / TRANSFER / DEBT_PAYMENT / DEBT_INTEREST).

Reemplaza al frozenset `INTEREST_CATEGORY_NAMES` (acoplado a strings
en español) y absorbe `is_transfer` en un atributo declarativo único.
`is_transfer` se mantiene en la columna durante PHASE-30.x para
compatibilidad — eliminación en una fase posterior cuando todos los
callers consuman `role`.

Backfill:
- `role=TRANSFER`        si `is_transfer=true`
- `role=DEBT_INTEREST`   si name ∈ {Intereses hipoteca, Intereses préstamo, Intereses tarjeta}
- `role=DEBT_PAYMENT`    si name ∈ {Préstamos e hipotecas, Tarjeta de crédito}
- `role=GENERIC`         resto

Idempotente: re-aplicar la migración no cambia roles ya asignados.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "s6i70k2gf5j3h9"
down_revision: str | None = "r5h69j1fe4i2g8"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Crear enum (idempotente con `checkfirst` que `create_type=False`
    #    evita; aquí usamos SQL directo para controlar el flujo).
    bind.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'categoryrole') THEN
                CREATE TYPE categoryrole AS ENUM (
                    'GENERIC', 'TRANSFER', 'DEBT_PAYMENT', 'DEBT_INTEREST'
                );
            END IF;
        END $$;
    """))

    # 2. Añadir columna NULLABLE inicialmente para backfill seguro.
    #    Si la columna ya existe (re-aplicación parcial), no la
    #    duplicamos.
    bind.execute(sa.text("""
        ALTER TABLE categories
        ADD COLUMN IF NOT EXISTS role categoryrole;
    """))

    # 3. Backfill — TRANSFER tiene prioridad sobre DEBT_* porque una
    #    categoría is_transfer no debería caer accidentalmente en
    #    DEBT_PAYMENT aunque su nombre matchee (caso teórico:
    #    "Préstamo a un amigo" categorizada is_transfer).
    bind.execute(sa.text("""
        UPDATE categories SET role = 'TRANSFER'
        WHERE is_transfer = TRUE AND role IS NULL;
    """))
    bind.execute(sa.text("""
        UPDATE categories SET role = 'DEBT_INTEREST'
        WHERE role IS NULL
          AND name IN (
              'Intereses hipoteca',
              'Intereses préstamo',
              'Intereses tarjeta'
          );
    """))
    bind.execute(sa.text("""
        UPDATE categories SET role = 'DEBT_PAYMENT'
        WHERE role IS NULL
          AND name IN (
              'Préstamos e hipotecas',
              'Tarjeta de crédito'
          );
    """))
    bind.execute(sa.text("""
        UPDATE categories SET role = 'GENERIC' WHERE role IS NULL;
    """))

    # 4. NOT NULL + default para nuevas filas.
    bind.execute(sa.text("""
        ALTER TABLE categories ALTER COLUMN role SET NOT NULL;
    """))
    bind.execute(sa.text("""
        ALTER TABLE categories ALTER COLUMN role SET DEFAULT 'GENERIC';
    """))

    # 5. Índice parcial para queries de "todas las categorías de deuda"
    #    (`role IN (DEBT_PAYMENT, DEBT_INTEREST)`). Acelera el filtro
    #    sin penalizar inserciones de categorías GENERIC/TRANSFER.
    bind.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS ix_categories_role_debt
        ON categories (user_id, role)
        WHERE role IN ('DEBT_PAYMENT', 'DEBT_INTEREST');
    """))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DROP INDEX IF EXISTS ix_categories_role_debt;"))
    bind.execute(sa.text("ALTER TABLE categories DROP COLUMN IF EXISTS role;"))
    bind.execute(sa.text("DROP TYPE IF EXISTS categoryrole;"))
