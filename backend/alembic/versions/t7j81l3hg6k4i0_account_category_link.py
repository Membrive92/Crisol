"""PHASE-30.4 — `accounts.category_id` FK nullable a `categories.id`.

Permite vincular una liability account con la categoría de pagos que
el usuario usa para clasificar sus cuotas en transacciones. Cruza
Capa 2 (contrato detallado) con Capa 1 (flujo categorizado).

Reglas de uso del campo viven en `accounts/service.py`:
- Sólo se acepta `category_id` en cuentas liability.
- La categoría debe pertenecer al usuario.
- La categoría debe tener `role IN (DEBT_PAYMENT, DEBT_INTEREST)`.

ON DELETE SET NULL — si el usuario borra la categoría, la cuenta sigue
existiendo sin vinculación. Idempotente.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "t7j81l3hg6k4i0"
down_revision: str | None = "s6i70k2gf5j3h9"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("""
        ALTER TABLE accounts
        ADD COLUMN IF NOT EXISTS category_id UUID
            REFERENCES categories(id) ON DELETE SET NULL;
    """))
    # Índice para queries del tipo "contratos vinculados a esta
    # categoría" (capa de detalle al clickar un segmento del donut en
    # PHASE-30.4 frontend).
    bind.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS ix_accounts_category_id
        ON accounts (category_id)
        WHERE category_id IS NOT NULL;
    """))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DROP INDEX IF EXISTS ix_accounts_category_id;"))
    bind.execute(sa.text("ALTER TABLE accounts DROP COLUMN IF EXISTS category_id;"))
