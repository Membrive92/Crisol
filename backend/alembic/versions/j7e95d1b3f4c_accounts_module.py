"""accounts — modelo de cuentas + account_id NOT NULL en transactions

Revision ID: j7e95d1b3f4c
Revises: i6d83e4f29a5
Create Date: 2026-05-10 00:00:00.000000

PHASE-19.1 — añade el modelo `accounts` y exige que cada transacción
pertenezca a una cuenta.

ATENCIÓN: esta migración borra todas las transacciones, import_jobs y
receipts existentes (DELETE en cascada manual antes de añadir la nueva
columna NOT NULL). La política se acordó con el usuario: el histórico se
reimporta desde cero tras crear las cuentas. Categorías, presupuestos,
gastos fijos y reglas se conservan intactos.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "j7e95d1b3f4c"
down_revision: str | None = "i6d83e4f29a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1) Tabla `accounts`. Los enums incluyen ya los `liability` (PHASE-20)
    #    para no requerir otro migration cuando llegue el módulo de deuda.
    op.create_table(
        "accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "BANK",
                "SAVINGS",
                "BROKERAGE",
                "CRYPTO",
                "CASH",
                "CREDIT_CARD",
                "LOAN",
                "MORTGAGE",
                name="accounttype",
            ),
            nullable=False,
        ),
        sa.Column(
            "nature",
            sa.Enum("ASSET", "LIABILITY", name="accountnature"),
            nullable=False,
            server_default="ASSET",  # alineado con `name` del Python enum (UPPER)
        ),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
            server_default="EUR",
        ),
        sa.Column("color", sa.String(length=7), nullable=True),
        sa.Column("icon", sa.String(length=50), nullable=True),
        sa.Column(
            "opening_balance",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default="0",
        ),
        sa.Column("opening_balance_date", sa.Date(), nullable=True),
        sa.Column(
            "display_order",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "is_archived",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_accounts_user_id"),
        "accounts",
        ["user_id"],
        unique=False,
    )

    # 2) Wipe del histórico que depende de transactions.
    #    Orden: receipts (FK SET NULL → tx) → import_jobs (sin FK) → transactions.
    #    Bank mappings, category rules, fixed expenses, budgets y categories
    #    se conservan — son configuración, no histórico.
    op.execute("DELETE FROM receipts")
    op.execute("DELETE FROM import_jobs")
    op.execute("DELETE FROM transactions")

    # 3) `account_id NOT NULL` en transactions con FK a accounts.
    #    Como la tabla quedó vacía tras el wipe, el NOT NULL no necesita default.
    op.add_column(
        "transactions",
        sa.Column("account_id", sa.Uuid(), nullable=False),
    )
    op.create_foreign_key(
        "fk_transactions_account_id",
        "transactions",
        "accounts",
        ["account_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        op.f("ix_transactions_account_id"),
        "transactions",
        ["account_id"],
        unique=False,
    )

    # 4) `account_id` opcional en `import_jobs` (para auditar a qué
    #    cuenta se importó cada lote) y en `fixed_expenses` (la cuenta
    #    desde la que se cobra el gasto fijo recurrente). Son nullables
    #    porque los fixed_expenses existentes pueden no tener cuenta
    #    todavía — el autopost sólo dispara si está asignada.
    op.add_column(
        "import_jobs",
        sa.Column("account_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_import_jobs_account_id",
        "import_jobs",
        "accounts",
        ["account_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_import_jobs_account_id"),
        "import_jobs",
        ["account_id"],
        unique=False,
    )

    op.add_column(
        "fixed_expenses",
        sa.Column("account_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_fixed_expenses_account_id",
        "fixed_expenses",
        "accounts",
        ["account_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_fixed_expenses_account_id"),
        "fixed_expenses",
        ["account_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_fixed_expenses_account_id"), table_name="fixed_expenses"
    )
    op.drop_constraint(
        "fk_fixed_expenses_account_id", "fixed_expenses", type_="foreignkey"
    )
    op.drop_column("fixed_expenses", "account_id")
    op.drop_index(
        op.f("ix_import_jobs_account_id"), table_name="import_jobs"
    )
    op.drop_constraint(
        "fk_import_jobs_account_id", "import_jobs", type_="foreignkey"
    )
    op.drop_column("import_jobs", "account_id")
    op.drop_index(
        op.f("ix_transactions_account_id"), table_name="transactions"
    )
    op.drop_constraint(
        "fk_transactions_account_id", "transactions", type_="foreignkey"
    )
    op.drop_column("transactions", "account_id")
    op.drop_index(op.f("ix_accounts_user_id"), table_name="accounts")
    op.drop_table("accounts")
    sa.Enum(name="accountnature").drop(op.get_bind(), checkfirst=False)
    sa.Enum(name="accounttype").drop(op.get_bind(), checkfirst=False)
