"""Fixtures globales de pytest para el backend.

Cada request HTTP crea su propia sesión (igual que producción), lo que evita
conflictos de concurrencia con asyncpg. Tras cada test, se truncan todas las
tablas para garantizar aislamiento.

Los tests usan SIEMPRE `settings.test_database_url`, una BD separada que
se crea on-demand. Nunca tocan la BD de desarrollo.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from unittest.mock import AsyncMock, patch

import asyncpg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import NullPool
from sqlalchemy import text as sa_text
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.modules.auth.models import RefreshToken  # noqa: F401
from app.modules.auth.webauthn.models import (  # noqa: F401
    WebAuthnChallenge,
    WebAuthnCredential,
)
from app.modules.currency.exceptions import FrankfurterUnavailableError
from app.modules.currency.models import ExchangeRate  # noqa: F401
from app.modules.investment.analysis.models import AnalysisRun  # noqa: F401
from app.modules.investment.catalog.directory_models import (  # noqa: F401
    ListingDirectoryEntry,
)
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
from app.modules.personal_finance.accounts.models import Account  # noqa: F401
from app.modules.personal_finance.bank_mappings.models import BankCategoryMapping  # noqa: F401
from app.modules.personal_finance.budgets.models import Budget  # noqa: F401
from app.modules.personal_finance.categories.models import Category  # noqa: F401
from app.modules.personal_finance.category_rules.models import CategoryRule  # noqa: F401
from app.modules.personal_finance.fixed_expenses.models import FixedExpense  # noqa: F401
from app.modules.personal_finance.imports.models import ImportJob  # noqa: F401
from app.modules.personal_finance.receipts.models import Receipt  # noqa: F401
from app.modules.personal_finance.transactions.models import Transaction  # noqa: F401
from app.modules.users.models import User  # noqa: F401


def _assert_isolated() -> None:
    """Sanity check: la BD de tests no puede coincidir con la de dev."""
    if settings.test_database_url == settings.database_url:
        raise RuntimeError(
            "test_database_url == database_url — los tests borrarían datos "
            "de desarrollo. Configura una BD separada en `.env`."
        )


async def _ensure_test_database_exists() -> None:
    """Crea la BD de tests si no existe.

    Conecta al cluster apuntando a la BD admin (`postgres` por defecto), no al
    propio target — `CREATE DATABASE` no se puede ejecutar dentro de la BD
    que se quiere crear ni dentro de una transacción.
    """
    url = make_url(settings.test_database_url)
    target_db = url.database
    if not target_db:
        raise RuntimeError("test_database_url no incluye nombre de base de datos")

    conn = await asyncpg.connect(
        host=url.host,
        port=url.port,
        user=url.username,
        password=url.password,
        database="postgres",
    )
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", target_db)
        if not exists:
            # Identificador, no parámetro — escapamos comillas para evitar
            # inyección si el nombre llegase configurado raro.
            safe_name = target_db.replace('"', '""')
            await conn.execute(f'CREATE DATABASE "{safe_name}"')
    finally:
        await conn.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine() -> AsyncIterator[None]:
    """Engine compartido para toda la sesión de tests.

    Crea las tablas al inicio y las elimina al final.
    """
    _assert_isolated()
    await _ensure_test_database_exists()

    engine = create_async_engine(settings.test_database_url, future=True, poolclass=NullPool)

    async with engine.begin() as conn:
        # `listing_directory` lleva un índice GIN con `gin_trgm_ops` y la
        # búsqueda usa `similarity()`: sin la extensión, el `create_all` y las
        # queries del directorio revientan. En prod la crea la migración; aquí
        # el schema sale de `create_all`, así que se crea antes.
        await conn.execute(sa_text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.run_sync(Base.metadata.create_all)

    try:
        yield engine  # type: ignore[misc]
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _offline_frankfurter(request) -> AsyncIterator[None]:  # type: ignore[no-untyped-def]
    """Bloquea el fetch real de tipos de cambio en TODA la suite.

    Varios caminos disparan `client.fetch_rates` sin que se vea en el test que
    los invoca: el dashboard cross-currency vía `ensure_rates_for_dates`, y
    desde PHASE-44.11 también `/portfolio/summary`, que exige la tasa del día y
    la pide si falta. Sin este bloqueo la suite depende de la red **y de la
    fecha real en que se ejecute**, que es la clase de test-bomba-de-relojería
    que ya mordió en AUDIT-2026-08.

    Vivía duplicado como fixture local en dos ficheros; está aquí porque la
    regla es de la suite entera, no de quien se acuerde de ponerlo. La única
    fuente de tasas en tests son los seeds explícitos.

    Los tests del PROPIO cliente se marcan con `@pytest.mark.real_fx_client`:
    parchearles `fetch_rates` sería parchear justo lo que quieren probar. No
    hacen red — mockean `httpx` por dentro.
    """
    if request.node.get_closest_marker("real_fx_client"):
        yield
        return
    with patch(
        "app.modules.currency.client.fetch_rates",
        new_callable=AsyncMock,
        side_effect=FrankfurterUnavailableError("suite offline"),
    ):
        yield


@pytest.fixture(autouse=True)
def _empty_symbol_index(request) -> Iterator[None]:  # type: ignore[no-untyped-def]
    """Deja el índice de emisores de la SEC VACÍO en toda la suite.

    Mismo motivo que el bloqueo de tipos de cambio de arriba: un test no debe
    depender de datos que no ha sembrado. El índice trae 10.365 emisores reales,
    así que sin esto una aserción tan inocente como «buscar `mc` devuelve MCD»
    empieza a recibir Moelis, McKesson y Metropolitan Bank — y se rompería con
    cada actualización de `edgartools` por motivos ajenos al código que prueba.

    Va aquí y no fichero a fichero porque el índice es un **singleton de
    proceso**: basta con que un test lo cargue para que todos los posteriores lo
    hereden, y entonces el resultado de la suite dependería del orden.

    Quien necesite el índice de verdad se marca con `real_symbol_index`; quien
    necesite filas concretas usa `symbol_index.set_index_for_tests`.
    """
    from app.modules.investment.catalog import symbol_index

    if request.node.get_closest_marker("real_symbol_index"):
        symbol_index.reset_index_for_tests()
        yield
        symbol_index.reset_index_for_tests()
        return

    symbol_index.set_index_for_tests(())
    yield
    symbol_index.reset_index_for_tests()


@pytest_asyncio.fixture(autouse=True)
async def clean_tables(test_engine) -> AsyncIterator[None]:  # type: ignore[no-untyped-def]
    """Trunca todas las tablas tras cada test para garantizar aislamiento."""
    yield
    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


@pytest_asyncio.fixture
async def client(test_engine) -> AsyncIterator[AsyncClient]:  # type: ignore[no-untyped-def]
    """Cliente HTTP asíncrono. Cada request obtiene su propia sesión."""
    test_session_factory = async_sessionmaker(
        bind=test_engine,
        expire_on_commit=False,
        autoflush=False,
    )

    async def override_get_db() -> AsyncIterator[None]:
        async with test_session_factory() as session:
            yield session  # type: ignore[misc]

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()
