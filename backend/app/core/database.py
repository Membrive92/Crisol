"""Conexión a la base de datos y fábrica de sesiones async.

Uso desde endpoints:

    @router.get("/…")
    async def handler(db: Annotated[AsyncSession, Depends(get_db)]):
        ...
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """Base declarativa de todos los modelos ORM."""


engine = create_async_engine(
    settings.database_url,
    echo=settings.app_debug,
    future=True,
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """Dependency de FastAPI que entrega una sesión async por request."""
    async with SessionLocal() as session:
        yield session
