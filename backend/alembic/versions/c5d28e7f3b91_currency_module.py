"""currency module — exchange_rates table + initial offline snapshot

Revision ID: c5d28e7f3b91
Revises: a91d8f4c2e10
Create Date: 2026-05-03 00:00:00.000000

"""
from collections.abc import Sequence
from datetime import date

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c5d28e7f3b91"
down_revision: str | None = "b27e391fa4c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exchange_rates",
        sa.Column("rate_date", sa.Date(), nullable=False),
        sa.Column("base", sa.String(length=3), nullable=False),
        sa.Column("quote", sa.String(length=3), nullable=False),
        # NUMERIC(20, 8) cubre desde tasas pequeñas (JPY ≈ 0.006 EUR/JPY
        # invertido) hasta pares grandes con precisión de centésima de
        # pip. El redondeo a 2 dec lo hace el service.
        sa.Column("rate", sa.Numeric(20, 8), nullable=False),
        sa.Column(
            "source",
            sa.String(length=32),
            nullable=False,
            server_default="frankfurter",
        ),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("rate_date", "base", "quote"),
    )
    op.create_index(
        "ix_exchange_rates_quote_date",
        "exchange_rates",
        ["quote", "rate_date"],
    )

    # Bootstrap offline. La importación se hace dentro de upgrade para
    # que la migración no dependa del módulo en su top-level (evita
    # ciclos cuando alembic se ejecuta con un PYTHONPATH ajustado).
    from app.modules.currency.seeds import load_snapshot

    rows = load_snapshot()
    if rows:
        op.bulk_insert(
            sa.table(
                "exchange_rates",
                sa.column("rate_date", sa.Date()),
                sa.column("base", sa.String(length=3)),
                sa.column("quote", sa.String(length=3)),
                sa.column("rate", sa.Numeric(20, 8)),
                sa.column("source", sa.String(length=32)),
            ),
            [
                {
                    "rate_date": date.fromisoformat(r["rate_date"]),
                    "base": r["base"],
                    "quote": r["quote"],
                    "rate": r["rate"],
                    "source": r["source"],
                }
                for r in rows
            ],
        )


def downgrade() -> None:
    op.drop_index("ix_exchange_rates_quote_date", table_name="exchange_rates")
    op.drop_table("exchange_rates")
