"""Punto de entrada de la aplicación FastAPI."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.scheduler import create_scheduler
from app.modules.ai.router import router as ai_router
from app.modules.auth.router import router as auth_router
from app.modules.auth.webauthn.router import router as webauthn_router
from app.modules.currency.router import router as currency_router
from app.modules.personal_finance.budgets.router import router as budgets_router
from app.modules.personal_finance.categories.router import router as categories_router
from app.modules.personal_finance.dashboard.router import router as dashboard_router
from app.modules.personal_finance.imports.router import router as imports_router
from app.modules.personal_finance.receipts.router import router as receipts_router
from app.modules.personal_finance.transactions.router import router as transactions_router


@asynccontextmanager
async def lifespan(app_: FastAPI) -> AsyncIterator[None]:
    """Lifespan del proceso: arranca el scheduler en startup, lo para en shutdown.

    Sólo afecta cuando `settings.enable_currency_cron=True`. En tests
    el flag se desactiva — además el conftest no propaga lifespan a
    `ASGITransport`, así que este código no se ejecuta.
    """
    scheduler = create_scheduler()
    if scheduler is not None:
        scheduler.start()
        # Stash para que tests / debugging puedan inspeccionarlo.
        app_.state.scheduler = scheduler
    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)


app = FastAPI(
    title="Finanzas App API",
    version="0.0.0",
    description="API del backend de Finanzas App.",
    debug=settings.app_debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(ai_router)
app.include_router(auth_router)
app.include_router(webauthn_router)
app.include_router(currency_router)
app.include_router(categories_router)
app.include_router(transactions_router)
app.include_router(dashboard_router)
app.include_router(budgets_router)
app.include_router(imports_router)
app.include_router(receipts_router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Health check — no toca base de datos.

    Usado por el contenedor y por los tests de smoke para verificar que el
    proceso está vivo y la app carga correctamente la configuración.
    """
    return {"status": "ok", "env": settings.app_env}
