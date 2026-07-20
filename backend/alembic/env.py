"""Alembic environment en modo async.

Usa el engine async de la aplicación (`app.core.database`) y lee la URL de
la base de datos desde `app.core.config.settings`, no desde alembic.ini.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.core.config import settings
from app.core.database import Base

# Importar TODOS los modelos para que `Base.metadata` esté completo:
# `alembic check` (parity modelo↔migración en CI) sólo es fiable si el
# metadata objetivo incluye cada tabla del dominio.
from app.modules.auth.models import RefreshToken  # noqa: F401
from app.modules.auth.webauthn.models import (  # noqa: F401
    WebAuthnChallenge,
    WebAuthnCredential,
)
from app.modules.currency.models import ExchangeRate  # noqa: F401
from app.modules.investment.analysis.models import AnalysisRun  # noqa: F401
from app.modules.investment.catalog.models import Security  # noqa: F401
from app.modules.investment.fundamentals.models import (  # noqa: F401
    FinancialStatement,
    IngestionJob,
    RestatementFlag,
)
from app.modules.investment.portfolio.models import (  # noqa: F401
    CorporateAction,
    DividendReceived,
    Lot,
    LotAdjustment,
    Sale,
    SaleAllocation,
)
from app.modules.investment.pricing.models import PriceQuote  # noqa: F401
from app.modules.investment.thresholds.models import ScoringThresholds  # noqa: F401
from app.modules.personal_finance.accounts.installments_model import (  # noqa: F401
    LiabilityInstallment,
)
from app.modules.personal_finance.accounts.models import Account  # noqa: F401
from app.modules.personal_finance.bank_mappings.models import (  # noqa: F401
    BankCategoryMapping,
)
from app.modules.personal_finance.budgets.models import Budget  # noqa: F401
from app.modules.personal_finance.categories.models import Category  # noqa: F401
from app.modules.personal_finance.category_rules.models import (  # noqa: F401
    CategoryRule,
)
from app.modules.personal_finance.fixed_expenses.models import (  # noqa: F401
    FixedExpense,
)
from app.modules.personal_finance.imports.models import ImportJob  # noqa: F401
from app.modules.personal_finance.receipts.models import Receipt  # noqa: F401
from app.modules.personal_finance.transactions.models import Transaction  # noqa: F401
from app.modules.users.models import User  # noqa: F401

# Config de Alembic (alembic.ini).
config = context.config

# Sobrescribe la URL con la del entorno (settings).
config.set_main_option("sqlalchemy.url", settings.database_url)

# Logging de alembic.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata objetivo para autogenerate.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Ejecuta migraciones en modo 'offline' (emite SQL a stdout)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Hook síncrono invocado por el engine async."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Ejecuta migraciones con el engine async de la app."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
