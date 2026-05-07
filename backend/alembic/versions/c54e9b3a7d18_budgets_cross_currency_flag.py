"""budgets: opt-in convert_other_currencies flag

Revision ID: c54e9b3a7d18
Revises: b32c8a4d5f17
Create Date: 2026-05-06 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "c54e9b3a7d18"
down_revision: str | None = "b32c8a4d5f17"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "budgets",
        sa.Column(
            "convert_other_currencies",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("budgets", "convert_other_currencies")
