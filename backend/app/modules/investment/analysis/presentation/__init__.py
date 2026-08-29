"""Capa de presentación del informe — PURA (PHASE-44.24.C).

Recibe un `AnalysisRun` **ya persistido** (sus JSONB tal cual) más lo que el
servicio le pasa del mundo de hoy —el `Security` y la resolución de umbrales
vigente— y devuelve lo que la pantalla necesita para leerlo: la distancia de
cada señal a su corte, el orden por severidad y la procedencia de la vara.

**Por qué al LEER y no dentro del run.** La tabla `analysis_runs` contiene, a la
vez, runs de todas las versiones del motor que han existido (lección
PHASE-44.16). Calculado aquí, el run de McDonald's de 1.0.0 y el de JNJ de 1.3.0
reciben su capa de lectura HOY, sin reejecutar nada. Persistido, sólo la tendrían
los runs futuros. Y cambiar una frase o un formato no puede exigir reejecutar el
motor: el run es reproducible por `engine_version + thresholds_version`, y una
frase no forma parte de esa reproducibilidad.

**Reglas duras**, las mismas que `engine/` y por el mismo motivo:

- Sin BD, sin red y **sin reloj**. Todo lo temporal entra por parámetro.
- Nada de `engine/` importa este paquete. La dependencia es en un solo sentido,
  y un gate lo afirma: al revés se crearía el ciclo
  `catalog → base_ratios → metrics → glossary → presentation → catalog`.
- Nunca se comparan los cortes como CADENA. Lo persistido llega como texto y con
  la escala de la columna (`"0.600000"`), y el motor tiene `Decimal("0.6")`:
  iguales como número y distintos como cadena.
"""

from __future__ import annotations

from app.modules.investment.analysis.presentation.diff import (
    BandChange,
    FlagChange,
    QuestionChange,
    RestatementNote,
    RunDiff,
    ScoreChange,
    diff_runs,
)
from app.modules.investment.analysis.presentation.distance import (
    SignalDistance,
    distance_to_cut,
)
from app.modules.investment.analysis.presentation.origin import (
    ThresholdProfile,
    profile_of,
    threshold_origin,
)
from app.modules.investment.analysis.presentation.rehydrate import rehydrate_thresholds
from app.modules.investment.analysis.presentation.report import (
    ReportLayer,
    ReportQuestion,
    ReportSignal,
    build_report,
)

__all__ = [
    "BandChange",
    "FlagChange",
    "QuestionChange",
    "ReportLayer",
    "ReportQuestion",
    "ReportSignal",
    "RestatementNote",
    "RunDiff",
    "ScoreChange",
    "SignalDistance",
    "ThresholdProfile",
    "build_report",
    "diff_runs",
    "distance_to_cut",
    "profile_of",
    "rehydrate_thresholds",
    "threshold_origin",
]
