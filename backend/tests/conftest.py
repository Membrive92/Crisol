"""Fixtures globales de pytest para el backend.

Cada test recibe una sesión bound a una transacción que se rollbackea al
finalizar — los tests nunca commitean en la base de datos real. Esta
convención está fijada en CLAUDE.md: nada de mocks de DB, integración real.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.database import get_db
from app.main import app


@pytest_asyncio.fixture(scope="session")
async def test_engine() -> AsyncIterator[None]:
    """Engine compartido para toda la sesión de tests."""
    engine = create_async_engine(settings.database_url, future=True)
    try:
        yield engine  # type: ignore[misc]
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncIterator[AsyncSession]:
    """Sesión async con transacción rolleada al finalizar el test."""
    connection: AsyncConnection = await test_engine.connect()
    transaction = await connection.begin()
    session_factory = async_sessionmaker(bind=connection, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """Cliente HTTP asíncrono con la sesión de test inyectada."""

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()
