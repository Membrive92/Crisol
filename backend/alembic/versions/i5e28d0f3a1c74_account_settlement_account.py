"""accounts: desde qué cuenta de activo se cobra un pasivo

Aditiva y reversible: una self-FK nullable.

El cargo que paga una deuda vive en la cuenta corriente, no en la deuda —
`find_mirror_charge` exige `account_id == source.account_id` justamente por eso—,
así que hasta ahora no había forma de saber qué cargo cierra el ciclo de qué
tarjeta. En julio de 2026 el usuario tenía 4 cargos de cierre y 6 pasivos: la
atribución era ambigua y ninguna columna la resolvía. Sin ella no hay invariante
de conservación del ciclo, ni detección automática (ADR-0011).

`ON DELETE SET NULL` y no CASCADE: borrar la cuenta del banco no puede llevarse
por delante la deuda; sólo deja de saberse desde dónde se cobraba.

Sin backfill: la atribución la declara el usuario. La app le PROPONE un candidato
contando los cargos que ya enlazó (PHASE-45) y lo precarga en el formulario, pero
escribirlo aquí a ciegas convertiría una propuesta en un dato — que es
exactamente la trampa del `default=1` de [PHASE-44.11].

Revision ID: i5e28d0f3a1c74
Revises: h4d17c9e2f0b63
Create Date: 2026-08-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "i5e28d0f3a1c74"
down_revision: str | None = "h4d17c9e2f0b63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("settlement_account_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_accounts_settlement_account_id",
        "accounts",
        "accounts",
        ["settlement_account_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_accounts_settlement_account_id", "accounts", type_="foreignkey"
    )
    op.drop_column("accounts", "settlement_account_id")
