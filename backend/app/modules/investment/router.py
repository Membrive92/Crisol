"""Router agregador del módulo Inversión (PHASE-44.7, ARCHITECTURE §5).

Prefijo `/investment`. Cada sub-feature (catálogo, fundamentales, análisis,
cartera, precios) monta su propio `APIRouter` con prefijo relativo; aquí se
componen en uno solo para que `main.py` registre el módulo con una línea.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.investment.analysis.router import router as analysis_router
from app.modules.investment.catalog.router import router as catalog_router
from app.modules.investment.fundamentals.router import router as fundamentals_router
from app.modules.investment.portfolio.router import router as portfolio_router
from app.modules.investment.pricing.router import router as pricing_router

router = APIRouter(prefix="/investment")
router.include_router(catalog_router)
router.include_router(fundamentals_router)
router.include_router(analysis_router)
router.include_router(portfolio_router)
router.include_router(pricing_router)
