"""Punto de entrada de la aplicación FastAPI."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.scheduler import create_scheduler
from app.modules.ai.router import router as ai_router
from app.modules.auth.router import router as auth_router
from app.modules.auth.webauthn.router import router as webauthn_router
from app.modules.currency.router import router as currency_router
from app.modules.personal_finance.accounts.router import router as accounts_router
from app.modules.personal_finance.bank_mappings.router import router as bank_mappings_router
from app.modules.personal_finance.budgets.router import router as budgets_router
from app.modules.personal_finance.categories.router import router as categories_router
from app.modules.personal_finance.category_rules.router import router as category_rules_router
from app.modules.personal_finance.dashboard.router import router as dashboard_router
from app.modules.personal_finance.debt.router import router as debt_router
from app.modules.personal_finance.fixed_expenses.router import router as fixed_expenses_router
from app.modules.personal_finance.imports.router import router as imports_router
from app.modules.personal_finance.receipts.router import router as receipts_router
from app.modules.personal_finance.seed.router import router as seed_router
from app.modules.personal_finance.transactions.router import router as transactions_router
from app.modules.personal_finance.transfers.router import router as transfers_router


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
    title="Crisol API",
    version="0.0.0",
    description="API del backend de Crisol.",
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

logger = logging.getLogger("crisol")


@app.middleware("http")
async def _security_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """AUDIT-2026-05 — cabeceras de seguridad en toda respuesta."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
    )
    if settings.auth_cookie_secure:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
        )
    return response


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """AUDIT-2026-05 — nunca devolver tracebacks al cliente; loguear server-side.

    Sólo intercepta errores NO controlados (500). `HTTPException` y los
    errores de validación de FastAPI siguen su propio handler con su
    `detail` específico.
    """
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Error interno del servidor."})


app.include_router(ai_router)
app.include_router(auth_router)
app.include_router(webauthn_router)
app.include_router(currency_router)
app.include_router(accounts_router)
app.include_router(categories_router)
app.include_router(transactions_router)
app.include_router(transfers_router)
app.include_router(dashboard_router)
app.include_router(debt_router)
app.include_router(budgets_router)
app.include_router(fixed_expenses_router)
app.include_router(imports_router)
app.include_router(receipts_router)
app.include_router(bank_mappings_router)
app.include_router(category_rules_router)
app.include_router(seed_router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Health check — no toca base de datos.

    Usado por el contenedor y por los tests de smoke para verificar que el
    proceso está vivo y la app carga correctamente la configuración.
    """
    return {"status": "ok", "env": settings.app_env}
