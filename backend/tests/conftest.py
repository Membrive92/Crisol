"""Fixtures globales de pytest para el backend.

Cada request HTTP crea su propia sesión (igual que producción), lo que evita
conflictos de concurrencia con asyncpg. Tras cada test, se truncan todas las
tablas para garantizar aislamiento.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.modules.auth.models import RefreshToken  # noqa: F401
from app.modules.users.models import User  # noqa: F401


@pytest_asyncio.fixture(scope="session")
async def test_engine() -> AsyncIterator[None]:
    """Engine compartido para toda la sesión de tests.

    Crea las tablas al inicio y las elimina al final.
    """
    engine = create_async_engine(settings.database_url, future=True, poolclass=NullPool)

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
