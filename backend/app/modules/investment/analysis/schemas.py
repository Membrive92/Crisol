"""Schemas Pydantic de análisis (PHASE-44.7)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.modules.investment.analysis.engine.metrics import MetricUnit
from app.modules.investment.enums import ThresholdDirection


class ScoreComponentHelpResponse(BaseModel):
    """Una variable de un score forense, con su nombre legible (PHASE-44.24.A).

    Existe porque la tarjeta de desglose imprimía la CLAVE del motor: en pantalla
    se leía `DSRI`, `TATA`, `P4_cfo_supera_beneficio`. Es el mismo defecto que las
    señales en crudo que PHASE-44.9 cerró, y el mismo arreglo: la etiqueta sale
    del engine, junto a la fórmula que calcula la variable.
    """

    key: str
    label: str
    what: str


class ScoreHelpResponse(BaseModel):
    """La ficha de un score forense: qué mide, por qué importa, cómo se lee."""

    key: str
    what: str
    why: str
    reading: str
    components: list[ScoreComponentHelpResponse] = Field(default_factory=list)
    """Vacío en los cuatro scores que no publican desglose por diseño
    (`accruals`, `F5`, `F6`, `FZ`): son un ratio único, no un agregado. La lista
    vacía es el dato — la pantalla dice «este score no tiene desglose» en vez de
    dejar al usuario buscando un desplegable que no existe."""


class FlagHelpResponse(BaseModel):
    """La ficha de una bandera del motor (PHASE-44.24.A.2).

    `how_to_verify` es el campo que la distingue de las demás fichas: dice DÓNDE
    mirar en las cuentas para confirmarla o descartarla. Sin él, una bandera es
    un oráculo — el usuario sabe que algo pasa y no qué hacer con ello.
    """

    key: str
    label: str
    what: str
    why: str
    reading: str
    how_to_verify: str


class HelpCatalogResponse(BaseModel):
    """Los textos de ayuda que NO caben en el catálogo de métricas.

    Estático (no toca BD): es contenido del motor, no datos del usuario. Viaja
    aparte del catálogo de métricas porque su unidad NO es la métrica —son las
    variables de un score y las banderas— y mezclarlos obligaría a inflar
    `MetricDefinitionResponse` con campos que sólo tienen sentido para ocho de
    sus sesenta y cuatro entradas.
    """

    scores: list[ScoreHelpResponse]
    flags: list[FlagHelpResponse]
    engine_version: str


class MetricDefinitionResponse(BaseModel):
    """Una entrada del catálogo de métricas del engine (PHASE-44.9).

    Existe porque hasta ahora el catálogo NO viajaba: el cliente tenía que
    escribir a mano la etiqueta de cada métrica, y tres de ellas acabaron
    mintiendo sobre el número que enseñaban (F5 se pintaba como «deuda
    emergente» siendo riesgo de fondo de comercio; D8 como «rentabilidad por
    dividendo» siendo margen de seguridad). Con el catálogo servido, la etiqueta
    tiene UNA sola fuente y no puede divergir.
    """

    model_config = {"from_attributes": True}

    key: str
    label: str
    family: str
    unit: MetricUnit
    """Escala de lectura: sin ella un `0,42` es indistinguible entre 42 %,
    0,42 veces y 42 días."""
    direction: ThresholdDirection | None
    """`None` = **sin banda absoluta**. NO significa «sana»: significa que no hay
    corte global que aplicar (un DSO de 45 días es excelente en retail y pésimo
    en software)."""
    low_alarm: Decimal | None
    low_ok: Decimal | None
    high_ok: Decimal | None
    high_alarm: Decimal | None
    model_variant: str | None
    note: str
    help: str = ""
    """PHASE-44.23 — qué mide y cómo se calcula, para la «i» del informe. Vive
    en el engine (`engine/glossary.py`) por la misma razón que la etiqueta: una
    definición escrita en la pantalla no la contrasta nadie con la fórmula, y
    así es como tres rótulos acabaron mintiendo sobre su propio número.

    Es el MISMO texto que `what`: se conserva para que un cliente anterior a
    PHASE-44.24 siga funcionando sin cambiar nada."""
    why: str = ""
    """PHASE-44.24 — por qué importa, con el sesgo de la tesis del usuario:
    seguridad del reparto, caja disponible, riesgo de recorte. Un gate mide que
    no sea una paráfrasis de `help`."""
    reading: str = ""
    """PHASE-44.24 — hacia dónde se lee y con qué matices: si usa medias de dos
    ejercicios, si no aplica a financieras, si el primer año sale degradado."""


class MetricCatalogResponse(BaseModel):
    items: list[MetricDefinitionResponse]
    engine_version: str
    """La versión que produjo ESTE catálogo. Si no coincide con la del run que
    se está pintando, las etiquetas pueden no corresponder."""


class StressParamsRequest(BaseModel):
    """Overrides de los escenarios de stress. Cualquiera omitido usa el default
    del DESIGN §5."""

    revenue_drops: list[Decimal] | None = Field(default=None, max_length=6)
    rate_shocks_bps: list[int] | None = Field(default=None, max_length=6)
    pct_variable_debt: Decimal | None = None


class RunRequest(BaseModel):
    stress_params: StressParamsRequest | None = None


class SignalDistanceResponse(BaseModel):
    """A qué distancia está una señal del corte que decide su banda.

    El TEXTO no se compone aquí: «a 3 pp del verde» para un margen y «2,1× dentro
    del rojo» para una cobertura son la misma información dicha por unidad, y
    quien sabe formatear por unidad es `packages/ui` — que además lo hace igual
    en las dos apps.
    """

    cut: Decimal | None
    absolute: Decimal | None
    relative: Decimal | None
    """`None` con el corte en cero y en las métricas de puntuación, donde la
    relativa no significa nada: los cortes del X-Score están en −1,04 y −0,25."""
    side: str
    """`inside` (dentro de su banda) | `outside` (ya la ha cruzado)."""
    next_band: str
    """Qué banda cruzaría si siguiera empeorando. Con cortes iguales nunca es
    `caution`: esa región es vacía."""
    missing_reason: str | None = None


class ReportSignalResponse(BaseModel):
    key: str
    status: str | None = None
    severity_rank: int
    """0 = la peor. Ya resuelto en el servidor para que las dos apps no
    reimplementen la comparación — y para que no puedan discrepar sobre cuál es
    la señal que más duele de la misma empresa."""
    distance: SignalDistanceResponse | None = None
    threshold_origin: str
    """De dónde salió la vara. `not_recorded` cuando el run no la registró para
    ESA métrica, que no es lo mismo que la genérica."""
    drove_verdict: bool = False
    """Si esta señal hizo cierta una condición de «Evitar» que se cumple.

    No es «está en rojo»: el escenario de stress tiñe su pregunta y no está en
    la matriz del sello (PHASE-44.25)."""
    evidence_sentences: list[str] = Field(default_factory=list)
    """Lo que da cuerpo a una señal sin número — hoy, los escenarios de stress
    que dejan de cubrir, con sus dos coberturas dentro."""


class NextCheckResponse(BaseModel):
    key: str
    text: str
    signal_key: str | None = None
    """La clave de la señal, para enlazar el bullet con su fila."""


class ConditionSignalResponse(BaseModel):
    """El enriquecimiento de una señal de la matriz: lo que se calcula al servir.

    El valor y la banda viajan dentro de la condición del run; aquí sólo va lo
    que el run no guarda, y la pantalla cruza por clave."""

    key: str
    distance: SignalDistanceResponse | None = None
    threshold_origin: str


class ReportSummaryResponse(BaseModel):
    """El sumario del Dictamen: la selección y sus frases, del servidor.

    Las claves viajan para que la pantalla pinte las filas con número, unidad y
    enlace; la prosa nombra sin números. Ausente en runs sin desglose."""

    concerns_intro: str = ""
    concern_keys: list[str] = Field(default_factory=list)
    concerns_overflow: int = 0
    strengths_intro: str = ""
    strength_keys: list[str] = Field(default_factory=list)
    strengths_overflow: int = 0
    stress_sentences: list[str] = Field(default_factory=list)
    stress_margin: str | None = None


class ReportWhyResponse(BaseModel):
    """Por qué este veredicto.

    Ausente (`null`) cuando el run no trae la matriz evaluada: componerlo con la
    regla de HOY afirmaría sobre aquel análisis algo que su motor no comprobó.
    """

    decided_by: list[str] = Field(default_factory=list)
    exit_sentence: str = ""
    models_disagree: str | None = None
    signals: list[ConditionSignalResponse] = Field(default_factory=list)


class ReportQuestionResponse(BaseModel):
    key: str
    evidence: str = "evaluated"
    """El estado en que se puede leer el veredicto: sólo uno de los cuatro es un
    color. Se publica para que la pantalla y la frase no puedan discrepar."""
    outcomes_recorded: bool = False
    sentence: str = ""
    signals: list[ReportSignalResponse]


class ThresholdProfileResponse(BaseModel):
    """Qué perfil de umbrales gobierna a este valor HOY.

    Lo emite el servidor entero en vez de dejar que la pantalla lo componga con
    `security.sector`: `profile_for` fusiona el perfil financiero por ENCIMA del
    sectorial, así que para una entidad financiera clasificada en otro sector
    esa etiqueta sería falsa — y por el prefijo SIC 67 ése es el estado normal
    de las socimis del catálogo.
    """

    effective: str
    sector: str
    is_financial: bool
    is_reit: bool


class ReportLayerResponse(BaseModel):
    """La capa de LECTURA de un run: no se persiste, se calcula al servirlo.

    Así un run de un motor anterior la recibe hoy sin reejecutar nada, y cambiar
    un formato no obliga a volver a calcular un análisis que sigue siendo
    válido.
    """

    threshold_profile: ThresholdProfileResponse
    questions: list[ReportQuestionResponse]
    narrative_version: str = ""
    """La versión de los TEXTOS, distinta de la del motor: reescribir una frase
    no cambia ningún número, así que no puede marcar como caducado un run."""
    headline: str = ""
    next_checks: list[NextCheckResponse] = Field(default_factory=list)
    why: ReportWhyResponse | None = None
    summary: ReportSummaryResponse | None = None


class AnalysisRunResponse(BaseModel):
    """El run completo, con scores en columnas y el desglose en JSONB."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    security_id: uuid.UUID
    run_date: datetime
    engine_version: str
    thresholds_version: str
    thresholds_used: dict[str, Any]
    """`metric_key → spec` con los cortes que se aplicaron en ESTE run. Vacío en
    los runs anteriores a PHASE-44.9: su calibración no es recuperable."""
    years_covered: list[int]

    m_score: Decimal | None
    z_score: Decimal | None
    z_variant: str | None
    f_score: int | None
    accruals_ratio: Decimal | None
    fcf_payout: Decimal | None
    fcf_coverage: Decimal | None
    dividend_verdict: str | None
    confidence: Decimal

    scores_detail: dict[str, Any]
    dividend_analysis: dict[str, Any]
    evolution: dict[str, Any]
    flags: list[dict[str, Any]]
    verdict: dict[str, Any]
    data_completeness: dict[str, Any]

    report: ReportLayerResponse | None = None
    """La capa de lectura (PHASE-44.24.C). `None` sólo si el servidor no la
    pudo construir; un cliente anterior la ignora y sigue funcionando."""


class AnalysisRunSummary(BaseModel):
    """Fila ligera para el histórico (sin el JSONB pesado)."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    run_date: datetime
    engine_version: str
    thresholds_version: str
    """Para etiquetar «comparable» en la lista SIN pedir los runs enteros.

    Dos análisis con distinto motor o distinta calibración no se pueden
    comparar como empresa (PHASE-44.24.F), y el selector tiene que poder
    decirlo antes de que el usuario elija."""
    years_covered: list[int]
    m_score: Decimal | None
    z_score: Decimal | None
    f_score: int | None
    dividend_verdict: str | None
    confidence: Decimal


class AnalysisRunListResponse(BaseModel):
    items: list[AnalysisRunSummary]


# ── Valoración por múltiplos (PHASE-44.12) ────────────────────────────


class ValuationMetricResponse(BaseModel):
    """Un múltiplo. `value` es `None` si y sólo si no se puede calcular, y
    entonces `reason` lo explica en español para el usuario."""

    model_config = {"from_attributes": True}

    key: str
    value: Decimal | None
    status: str
    reason: str | None


class ValuationResponse(BaseModel):
    """Los múltiplos de un valor contra su cotización.

    NO sale del `AnalysisRun` y no se persiste: se calcula al vuelo cruzando el
    último ejercicio con el precio del momento. Por eso lleva las dos fechas
    —`quote_as_of` y `fiscal_year_end`— bien visibles: un PER con precio de hoy
    sobre un beneficio de hace catorce meses no es falso, pero tiene que decirlo.
    """

    available: bool
    reason: str | None
    """Por qué no hay múltiplos. `None` cuando sí los hay."""
    price_is_override: bool
    """El precio lo puso el usuario, no el proveedor. Se declara para que un
    precio simulado no se confunda con uno de mercado."""

    metrics: list[ValuationMetricResponse] = Field(default_factory=list)
    fiscal_year: int | None = None
    fiscal_year_end: date | None = None
    statement_currency: str | None = None
    market_cap: Decimal | None = None
    enterprise_value: Decimal | None = None
    quote_as_of: date | None = None
    quote_stale: bool = False
    provider_status: str = "cached"
    """Estado del proveedor de cotizaciones en ESTA consulta:

    - `live` — se le ha pedido y ha respondido.
    - `cached` — no se le ha pedido (la cotización guardada seguía fresca), así
      que de su estado no se sabe nada.
    - `unreachable` — se le ha pedido y ha fallado; se sirve el último precio
      registrado.
    """
    fx_rate: Decimal | None = None
    fx_as_of: date | None = None
    days_since_fiscal_year_end: int | None = None
    staleness: str | None = None
    """`null` | `aging` (≥9 meses) | `stale` (≥18 meses)."""
    notes: list[str] = Field(default_factory=list)


# ── Comparador de runs (PHASE-44.24.F) ────────────────────────────────


class ScoreChangeResponse(BaseModel):
    key: str
    before: str | None
    after: str | None
    band_before: str | None
    band_after: str | None


class BandChangeResponse(BaseModel):
    key: str
    band_before: str | None
    band_after: str | None
    value_before: str | None
    value_after: str | None


class FlagChangeResponse(BaseModel):
    key: str
    label: str | None
    severity: str | None
    appeared: bool


class QuestionChangeResponse(BaseModel):
    key: str
    verdict_before: str | None
    verdict_after: str | None
    evidence_before: str
    evidence_after: str


class RestatementNoteResponse(BaseModel):
    fiscal_year: int
    filing_a: str
    filing_b: str
    item_count: int


class RunDiffResponse(BaseModel):
    """Qué ha cambiado entre dos análisis de la misma empresa.

    `comparable=False` significa que el MÉTODO cambió (motor o calibración) y
    entonces las listas de cambios de empresa vienen VACÍAS por construcción:
    leer un cambio de banda como una degradación del negocio cuando lo que se
    movió fue el corte es la conclusión equivocada.
    """

    comparable: bool
    base_id: uuid.UUID
    target_id: uuid.UUID
    base_date: datetime | None
    target_date: datetime | None
    method_changes: list[str]
    years_added: list[int]
    years_removed: list[int]
    safety_before: str | None
    safety_after: str | None
    dividend_before: str | None
    dividend_after: str | None
    questions: list[QuestionChangeResponse]
    scores: list[ScoreChangeResponse]
    bands: list[BandChangeResponse]
    flags: list[FlagChangeResponse]
    restatements: list[RestatementNoteResponse]
    caveat: str | None
