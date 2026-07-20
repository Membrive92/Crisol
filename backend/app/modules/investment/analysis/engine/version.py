"""Versión del engine (PHASE-44.2, ARCHITECTURE §4.3, [Dec.7]).

`ENGINE_VERSION` es semver y se incrementa con **cualquier cambio de fórmula o
incorporación de métrica**. Viaja a cada `AnalysisRun` para que un informe
guardado sepa con qué matemática se calculó — sin eso, comparar dos runs de
fechas distintas es comparar peras con manzanas.

El golden test (ARCHITECTURE §7) falla si el output del engine cambia sin que
esta constante se mueva: es el gate que impide tocar una fórmula en silencio.

Historial:
- 1.0.0 — PHASE-44.2: Capa 1 (derivaciones §4.4 + 27 métricas base §5).
"""

from __future__ import annotations

ENGINE_VERSION = "1.0.0"
