"""webauthn_challenges.user_id nullable + relax FK for conditional UI

Hace `user_id` opcional en la tabla de challenges para soportar el flujo
de "Conditional UI" (passkey autofill sin email). En ese flujo, el
challenge se emite sin saber el usuario; al verificar, se identifica
al usuario por el `credential_id` de la respuesta.

Revision ID: b27e391fa4c8
Revises: d18a4c75b2e9
Create Date: 2026-04-29 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b27e391fa4c8"
down_revision: str | None = "d18a4c75b2e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "webauthn_challenges",
        "user_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "webauthn_challenges",
        "user_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
