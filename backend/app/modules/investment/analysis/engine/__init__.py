"""Engine de análisis fundamental — **PURO**: sin BD, sin red, sin reloj.

Regla dura (ARCHITECTURE §0.1): nada dentro de `engine/` importa SQLAlchemy,
httpx ni `datetime.now()`. Todo lo temporal entra por `StatementSeries.as_of`.
Eso es lo que permite testear cada métrica con statements sintéticos de importes
conocidos, sin levantar Postgres ni mockear red.

Capas (DESIGN §5) — se construyen en fases sucesivas:
  Capa 1   `base_ratios`  ✅ PHASE-44.2 (L*, A*, S*, R*)
  Capa 1.5 `evolution`    ⏳ horizontal, vertical, coherencia
  Capa 2   `forensic`     ⏳ M-score, Z'', F-score, accruals
  Capa 3   `dividend`     ⏳ D*, Q*, B*, T*
  Capa 3.5 `stress`       ⏳ shocks paramétricos
  Capa 4   `synthesis`    ⏳ matriz de banderas, veredicto, confianza
"""

from __future__ import annotations

from app.modules.investment.analysis.engine.version import ENGINE_VERSION

__all__ = ["ENGINE_VERSION"]
