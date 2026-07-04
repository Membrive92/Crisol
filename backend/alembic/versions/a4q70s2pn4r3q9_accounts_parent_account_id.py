"""PHASE-35 — `accounts.parent_account_id` (compras a plazos bajo una tarjeta).

Permite que una tarjeta de crédito agrupe VARIAS compras financiadas, cada
una con su propio TIN/TAE/plazo/cuadro de amortización. Cada compra es una
cuenta-deuda hija con `parent_account_id` apuntando a la tarjeta padre.

Puramente aditiva: columna nullable (NULL = cuenta normal, comportamiento
previo intacto) + índice parcial para agrupar las hijas por su tarjeta.
`ON DELETE CASCADE`: borrar la tarjeta arrastra sus compras a plazos.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "a4q70s2pn4r3q9"
down_revision: str | None = "z3p58r0on2q1p7"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("parent_account_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_accounts_parent_account_id",
        "accounts",
        "accounts",
        ["parent_account_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_accounts_parent_account_id",
        "accounts",
        ["parent_account_id"],
        unique=False,
        postgresql_where=sa.text("parent_account_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_accounts_parent_account_id", table_name="accounts")
    op.drop_constraint("fk_accounts_parent_account_id", "accounts", type_="foreignkey")
    op.drop_column("accounts", "parent_account_id")
