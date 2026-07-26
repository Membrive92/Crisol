"""Contrato del adapter de fundamentales (PHASE-44.6, ARCHITECTURE §3.1).

Un adapter hace DOS cosas: identificar el valor (ticker → CIK y metadatos) y
traer sus hechos XBRL. Todo lo demás —anclar los hechos a ejercicios, mapear a
partidas canónicas, cuadrar— es puro y vive fuera (`annual.py`,
`normalization.py`, `validation.py`), para que cambiar de proveedor no arrastre
la inteligencia del módulo.

## Desviación del contrato escrito en la ARCHITECTURE

El §3.1 preveía tres métodos: `resolve` → `list_annual_filings` → `fetch_filing`,
uno por filing. Con la API `companyfacts` de la SEC —la que usa `edgartools` para
construir su modelo de hechos— eso serían N descargas del mismo payload: la SEC
devuelve TODOS los hechos de la empresa en una sola respuesta, y cada hecho trae
el `accession` que lo reportó. Así que se descarga una vez y la lista de filings
se DERIVA de los hechos (`annual.filing_refs`), que además es la única forma de
saber qué ejercicio reexpresó cada filing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

from app.modules.investment.fundamentals.adapters.concept_map import qualify


@dataclass(frozen=True)
class SecurityIdentity:
    """Quién es la empresa, con lo que el engine necesita para elegir modelos.

    `is_financial` desactiva los forenses (Beneish y Altman no aplican a bancos)
    e `is_reit` activa la rama FFO de la capa 3, así que no son metadatos
    decorativos: cambian qué se calcula.
    """

    ticker: str
    cik: str
    name: str
    sic: str | None = None
    is_reit: bool = False
    is_financial: bool = False
    annual_report_count: int | None = None
    """Cuántos 10-K presenta el emisor (PHASE-44.8).

    `None` significa «el adapter no lo comprobó», NO «no tiene»: la ausencia de
    evidencia no es evidencia de ausencia, y quien la reciba debe tratarla como
    desconocida en vez de bloquear el valor. Sólo un `0` explícito afirma que no
    hay 10-K."""

    foreign_annual_report_count: int | None = None
    """Cuántos 20-F presenta el emisor, con la misma semántica de `None`.

    Separa dos ceros que significan cosas distintas y que el usuario vive de
    forma distinta: SPY no presenta NI 10-K ni 20-F (es un vehículo, no una
    empresa), mientras que Santander presenta 25 veintiefes — publica cuentas
    anuales perfectamente, sólo que con taxonomía IFRS, que es un mapa que este
    módulo no tiene. Decirle a alguien que Santander "no publica cuentas" sería
    sencillamente falso."""


@dataclass(frozen=True)
class XbrlFact:
    """Un hecho XBRL, ya despegado del modelo del proveedor.

    Existe para que `annual.py` sea puro y testeable con sintéticos: la lógica de
    anclaje no debe conocer los tipos de `edgartools`. La conversión vive en el
    adapter, en un solo sitio.
    """

    taxonomy: str
    concept: str
    value: Decimal
    unit: str
    period_end: date
    period_start: date | None
    form_type: str
    fiscal_period: str
    fiscal_year: int
    accession: str
    filing_date: date

    @property
    def key(self) -> str:
        """La clave con namespace que espera `normalization.py`."""
        return qualify(self.taxonomy, self.concept)

    @property
    def is_instant(self) -> bool:
        """Un saldo (balance) frente a un flujo (resultados, caja)."""
        return self.period_start is None

    @property
    def duration_days(self) -> int | None:
        if self.period_start is None:
            return None
        return (self.period_end - self.period_start).days


@dataclass(frozen=True)
class FilingRef:
    """Un 10-K concreto: el ejercicio que reporta como principal y cuándo se
    presentó. Se deriva de los hechos, no se pide aparte."""

    accession: str
    filing_date: date
    fiscal_year: int
    fiscal_year_end: date
    form_type: str


class FundamentalsAdapter(Protocol):
    """Lo que tiene que saber hacer una fuente de fundamentales."""

    async def resolve(self, ticker: str) -> SecurityIdentity:
        """Ticker → identidad. Falla con mensaje claro si no existe."""
        ...

    async def fetch_facts(self, identity: SecurityIdentity) -> tuple[XbrlFact, ...]:
        """Todos los hechos anuales de la empresa, sin interpretar."""
        ...
