"""AUDIT-2026-05 — refresh tokens auto-identificables (token_id + family_id).

Rediseño del esquema de refresh tokens para eliminar el escaneo O(N) con un
argon2 verify por fila en cada /auth/refresh|logout: ahora cada token es
`<token_id>.<secret>`, se localiza por `token_id` indexado (1 query + 1
verify) y `family_id` da linaje para detectar reutilización (señal de robo).

INVALIDA todas las sesiones existentes: los tokens previos no tienen
`token_id`/`family_id` y no son utilizables bajo el nuevo esquema, así que se
borran (los usuarios vuelven a loguearse una vez). Idempotente.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "u8k92m4ih7l5j1"
down_revision: str | None = "t7j81l3hg6k4i0"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    bind = op.get_bind()
    # Los tokens previos quedan invalidados por el cambio de esquema.
    bind.execute(sa.text("DELETE FROM refresh_tokens;"))
    bind.execute(
        sa.text(
            "ALTER TABLE refresh_tokens "
            "ADD COLUMN IF NOT EXISTS token_id VARCHAR(64) NOT NULL, "
            "ADD COLUMN IF NOT EXISTS family_id UUID NOT NULL;"
        )
    )
    bind.execute(
        sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_refresh_tokens_token_id "
            "ON refresh_tokens (token_id);"
        )
    )
    bind.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_refresh_tokens_family_id "
            "ON refresh_tokens (family_id);"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DROP INDEX IF EXISTS ix_refresh_tokens_family_id;"))
    bind.execute(sa.text("DROP INDEX IF EXISTS ix_refresh_tokens_token_id;"))
    bind.execute(
        sa.text(
            "ALTER TABLE refresh_tokens "
            "DROP COLUMN IF EXISTS family_id, "
            "DROP COLUMN IF EXISTS token_id;"
        )
    )
