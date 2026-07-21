"""Catálogo agregado de métricas del engine (PHASE-44.3).

Une los catálogos de las tres capas implementadas en UNA lista. Es lo que
consumirá `thresholds/seed.py` para sembrar `scoring_thresholds`: mientras el
seed se construya desde aquí, las `metric_key` de la BD no pueden divergir de
las que el engine calcula [Dec.8].

Cuando lleguen las capas 3, 3.5 y 4, sus catálogos se suman en este mismo sitio.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.modules.investment.analysis.engine import base_ratios, dividend, evolution, forensic
from app.modules.investment.analysis.engine.metrics import MetricDefinition, thresholds_from
from app.modules.investment.analysis.engine.types import ThresholdSpec

ALL_METRIC_DEFINITIONS: tuple[MetricDefinition, ...] = (
    base_ratios.METRIC_CATALOG
    + evolution.METRIC_CATALOG
    + forensic.METRIC_CATALOG
    + dividend.METRIC_CATALOG
)

ALL_METRIC_KEYS: tuple[str, ...] = tuple(definition.key for definition in ALL_METRIC_DEFINITIONS)

ALL_DEFAULT_THRESHOLDS: Mapping[str, ThresholdSpec] = thresholds_from(ALL_METRIC_DEFINITIONS)
"""Bandas por defecto (US-GAAP genérico) de todas las capas juntas. `compute` de
cada capa acepta este mapa entero: cada una coge las suyas y ignora el resto."""


def definition_for(metric_key: str) -> MetricDefinition | None:
    for definition in ALL_METRIC_DEFINITIONS:
        if definition.key == metric_key:
            return definition
    return None
