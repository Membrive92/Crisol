"""Punto de entrada de la aplicación FastAPI."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.modules.ai.router import router as ai_router

app = FastAPI(
    title="Finanzas App API",
    version="0.0.0",
    description="API del backend de Finanzas App.",
    debug=settings.app_debug,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(ai_router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Health check — no toca base de datos.

    Usado por el contenedor y por los tests de smoke para verificar que el
    proceso está vivo y la app carga correctamente la configuración.
    """
    return {"status": "ok", "env": settings.app_env}
