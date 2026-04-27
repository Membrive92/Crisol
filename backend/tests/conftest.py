"""Fixtures globales de pytest para el backend.

Cada request HTTP crea su propia sesión (igual que producción), lo que evita
conflictos de concurrencia con asyncpg. Tras cada test, se truncan todas las
tablas para garantizar aislamiento.

Los tests usan SIEMPRE `settings.test_database_url`, una BD separada que
se crea on-demand. Nunca tocan la BD de desarrollo.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import asyncpg
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import NullPool
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.modules.auth.models import RefreshToken  # noqa: F401
from app.modules.imports.models import ImportJob  # noqa: F401
from app.modules.personal_finance.categories.models import Category  # noqa: F401
from app.modules.personal_finance.transactions.models import Transaction  # noqa: F401
from app.modules.receipts.models import Receipt  # noqa: F401
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
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", target_db
        )
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

    engine = create_async_engine(
        settings.test_database_url, future=True, poolclass=NullPool
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        yield engine  # type: ignore[misc]
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


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
