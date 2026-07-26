"""Adapter EDGAR (PHASE-44.6, ARCHITECTURE §3.2).

Reparte el trabajo entre `edgartools` y nosotros según quién debe responder de
qué:

- **`edgartools` identifica y parsea**: resuelve el ticker y aporta lo que cuesta
  deducir a mano (SIC, sector, si es REIT, si es una financiera) y convierte el
  JSON de la SEC en hechos con periodo, unidad y `accession`.
- **Nosotros descargamos y guardamos el crudo**: el payload `companyfacts` es la
  evidencia de auditoría (Dec.18) y tiene que quedarse en `EDGAR_CACHE_DIR` tal y
  como llegó. `edgartools` no lo devuelve —lo parsea por dentro—, así que la
  descarga es nuestra, con la identidad SEC en el `User-Agent` y serializada.
- **Nosotros anclamos**: `annual.py` decide qué hecho pertenece a qué ejercicio,
  porque la semántica de periodos de la librería no sirve para lo que necesita el
  análisis (ver el docstring de `annual.py`).

## La identidad se fija SIEMPRE de forma explícita

Si `edgartools` no encuentra identidad configurada, la pide por consola con
`input()`. En un backend eso no es un error visible: es una petición colgada para
siempre contra un stdin que nadie va a rellenar. Por eso el adapter la fija en el
constructor y falla en el acto con un mensaje accionable si no la tiene.
"""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx

from app.modules.investment.fundamentals.adapters.base import SecurityIdentity, XbrlFact
from app.modules.investment.fundamentals.cache import FactsCache

FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

_REIT_SIC_CODES: frozenset[str] = frozenset({"6798"})
"""SIC 6798 = Real Estate Investment Trusts. Es la señal DOCUMENTAL de que hay
que analizar por FFO en vez de por beneficio contable (la amortización de
inmuebles distorsiona el resultado de un REIT)."""

_FINANCIAL_SIC_PREFIXES: tuple[str, ...] = ("60", "61", "62", "63", "64", "67")
"""Bancos, crédito, valores, seguros y holdings financieros. Marca la exclusión
de los modelos forenses: Beneish y Altman se calibraron sobre empresas no
financieras y en un banco dan números sin significado."""


class EdgarIdentityMissingError(RuntimeError):
    """Falta `EDGAR_IDENTITY`. La SEC la exige en el `User-Agent`."""


class EdgarUnavailableError(RuntimeError):
    """La SEC no respondió o no tiene datos de esta empresa."""


def _bare_concept(concept: str) -> str:
    """`'us-gaap:Assets'` → `'Assets'`.

    `edgartools` devuelve el concepto YA cualificado, mientras que `taxonomy`
    viene aparte. Si se pasara tal cual, `XbrlFact.key` compondría
    `'us-gaap:us-gaap:Assets'` y NINGUNA partida canónica encontraría su
    concepto: el resultado no sería un error, sería una empresa entera en
    blanco. Se recorta aquí, en la frontera, y el resto del módulo trabaja
    siempre con el nombre desnudo.
    """
    return concept.split(":", 1)[-1]


def to_xbrl_fact(fact: Any) -> XbrlFact | None:
    """`FinancialFact` de `edgartools` → nuestro `XbrlFact`.

    Devuelve `None` para lo que no es un importe utilizable (valores de texto,
    hechos sin periodo). El importe se convierte desde el valor ORIGINAL vía
    `str`, no desde el `numeric_value` que la librería expone como `float`:
    `Decimal(str(56_147_000_000))` es exacto, mientras que pasar por un flotante
    mete un error de representación en cifras que luego se restan entre sí.
    """
    value = getattr(fact, "value", None)
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        amount = Decimal(str(value))
    except ArithmeticError:
        return None

    period_end = getattr(fact, "period_end", None)
    filing_date = getattr(fact, "filing_date", None)
    if not isinstance(period_end, date) or not isinstance(filing_date, date):
        return None

    return XbrlFact(
        taxonomy=str(getattr(fact, "taxonomy", "")),
        concept=_bare_concept(str(getattr(fact, "concept", ""))),
        value=amount,
        unit=str(getattr(fact, "unit", "")),
        period_end=period_end,
        period_start=getattr(fact, "period_start", None),
        form_type=str(getattr(fact, "form_type", "")),
        fiscal_period=str(getattr(fact, "fiscal_period", "")),
        fiscal_year=int(getattr(fact, "fiscal_year", 0) or 0),
        accession=str(getattr(fact, "accession", "")),
        filing_date=filing_date,
    )


def classify_sic(sic: str | None) -> tuple[bool, bool]:
    """SIC → (es REIT, es financiera). Sin SIC, ninguna de las dos.

    Ante la duda NO se marca: marcar de más apaga los forenses en una empresa
    normal (se pierde análisis), pero marcar de menos los corre en un banco y
    devuelve un veredicto con números que no significan nada — que es peor.
    """
    if not sic:
        return False, False
    code = sic.strip()
    return code in _REIT_SIC_CODES, code.startswith(_FINANCIAL_SIC_PREFIXES)


class EdgarAdapter:
    """Implementación de `FundamentalsAdapter` sobre EDGAR."""

    def __init__(
        self,
        *,
        identity: str,
        cache_dir: Path,
        timeout_seconds: int = 60,
    ) -> None:
        self.identity = identity.strip()
        self.cache = FactsCache(cache_dir)
        self.timeout_seconds = timeout_seconds

    def _require_identity(self) -> str:
        """La identidad, o un error claro. Y la fija en `edgartools` de paso.

        Se exige al SALIR A LA RED, no al construir el adapter: con el crudo ya
        cacheado se puede reingerir entero sin identidad y sin tocar la SEC, que
        es justo para lo que sirve guardar el crudo (re-derivar tras cambiar el
        mapeo, montar fixtures, reproducir un análisis viejo).

        Fijarla en `edgartools` aquí es lo que impide que la librería la pida por
        consola: en un backend, ese `input()` no es un error visible sino una
        petición colgada para siempre.
        """
        if not self.identity:
            raise EdgarIdentityMissingError(
                "Falta EDGAR_IDENTITY. La SEC exige identificarse en el User-Agent con "
                "'Nombre email' para descargar datos. Configúrala en el .env del backend "
                "(no hace falta si los datos ya están en la cache local)."
            )
        import edgar

        edgar.set_identity(self.identity)
        return self.identity

    @property
    def _headers(self) -> dict[str, str]:
        return {"User-Agent": self.identity, "Accept-Encoding": "gzip, deflate"}

    async def resolve(self, ticker: str) -> SecurityIdentity:
        """Ticker → identidad, con los metadatos que deciden qué modelos aplican."""
        self._require_identity()
        company = await asyncio.to_thread(self._load_company, ticker)
        sic = getattr(company, "sic", None)
        sic_code = str(sic) if sic else None
        is_reit, is_financial = classify_sic(sic_code)
        # `is_financial_institution` es un MÉTODO en edgartools, no un atributo:
        # leerlo con getattr sin llamarlo devuelve el objeto método —siempre
        # truthy— y marcaría a TODA empresa como financiera, apagando los
        # forenses (M-Score, Z, F-Score) hasta en una restauración o una
        # farmacéutica. El `callable` sobrevive a que la librería lo convierta en
        # propiedad en una versión futura.
        financial_flag = getattr(company, "is_financial_institution", False)
        if callable(financial_flag):
            financial_flag = financial_flag()
        if financial_flag:
            is_financial = True
        if getattr(company, "reit_subtype", None):
            is_reit = True
        return SecurityIdentity(
            ticker=ticker.upper(),
            cik=FactsCache.normalize_cik(company.cik),
            name=str(getattr(company, "name", "") or ticker.upper()),
            sic=sic_code,
            is_reit=is_reit,
            is_financial=is_financial,
            annual_report_count=await asyncio.to_thread(self._count_filings, company, "10-K"),
            foreign_annual_report_count=await asyncio.to_thread(
                self._count_filings, company, "20-F"
            ),
        )

    @staticmethod
    def _count_filings(company: Any, form: str) -> int | None:
        """Cuántos filings de ese formulario presenta la empresa, o `None` si no
        se puede saber.

        Es lo que separa una empresa de un vehículo, y a un emisor extranjero de
        ambos. Verificado ejecutando la librería contra la SEC de verdad:

            MCD    10-K=33   20-F=0     → una empresa US: analizable
            SPY    10-K=0    20-F=0     → un trust: no publica cuentas de empresa
            SAN    10-K=0    20-F=25    → publica, pero en IFRS
            ASML   10-K=0    20-F=27    → idem

        Sin esta cuenta, elegir SPY creaba un `Security` que luego no se podía
        analizar y el usuario sólo veía "lanza la ingesta primero" en bucle.

        Guarda `callable` porque un atributo que resulta ser método siempre es
        truthy (lección PHASE-44.6), y se traga los fallos devolviendo `None`
        —desconocido— porque un problema de red al CONTAR no debe impedir dar de
        alta un valor: sin evidencia, la regla de capacidades se comporta como
        antes de existir esta comprobación.
        """
        getter = getattr(company, "get_filings", None)
        if not callable(getter):
            return None
        try:
            return len(getter(form=form))
        except Exception:
            # Contar es opcional y nunca debe bloquear el alta de un valor.
            return None

    @staticmethod
    def _load_company(ticker: str) -> Any:
        """`edgar.Company` es síncrono y pega a la red: va en un hilo aparte.

        Un ticker que la SEC no conoce NO devuelve un objeto vacío: `edgartools`
        lanza `CompanyNotFoundError` desde el constructor (`entity/core.py`, cuando
        `find_cik` devuelve `None`). Sin capturarla, subía sin traducir y el
        endpoint respondía **500** pese a que su docstring promete un 404 — el
        usuario recibía "error interno" por haberse equivocado al teclear.

        Se captura por su tipo, importándola del paquete raíz (verificado:
        `edgar.CompanyNotFoundError`, hereda de `Exception` a secas, así que no hay
        un `ValueError` que atrapar por casualidad).
        """
        from edgar import Company, CompanyNotFoundError

        try:
            company = Company(ticker.upper())
        except CompanyNotFoundError as exc:
            raise EdgarUnavailableError(f"La SEC no conoce el ticker '{ticker}'.") from exc
        if company is None or getattr(company, "not_found", False):
            raise EdgarUnavailableError(f"La SEC no conoce el ticker '{ticker}'.")
        return company

    async def fetch_facts(
        self, identity: SecurityIdentity, *, refresh: bool = False
    ) -> tuple[XbrlFact, ...]:
        """Todos los hechos de la empresa, desde la cache o desde la SEC.

        `refresh=True` fuerza la descarga; por defecto la cache manda, porque un
        filing publicado no cambia y así una reingesta no le cuesta ni una
        petición a la SEC.
        """
        payload = None if refresh else self.cache.load(identity.cik)
        if payload is None:
            payload = await self._download_facts(identity.cik)
        return await asyncio.to_thread(self._parse_facts, payload, identity)

    async def _download_facts(self, cik: str) -> dict[str, Any]:
        """Descarga `companyfacts` y guarda el crudo antes de interpretarlo."""
        self._require_identity()
        url = FACTS_URL.format(cik=FactsCache.normalize_cik(cik))
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            try:
                response = await client.get(url, headers=self._headers)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    raise EdgarUnavailableError(
                        f"La SEC no tiene datos XBRL para el CIK {cik}. Suele pasar con "
                        "emisores extranjeros que no presentan en us-gaap."
                    ) from exc
                raise EdgarUnavailableError(
                    f"La SEC respondió {exc.response.status_code} al pedir los datos del "
                    f"CIK {cik}."
                ) from exc
            except httpx.HTTPError as exc:
                raise EdgarUnavailableError(
                    f"No se pudo contactar con data.sec.gov: {exc}"
                ) from exc

        self.cache.store(cik, response.content)
        loaded = self.cache.load(cik)
        if loaded is None:  # pragma: no cover — solo si el disco falla al releer
            raise EdgarUnavailableError(f"No se pudo guardar la descarga del CIK {cik}.")
        return loaded

    @staticmethod
    def _parse_facts(payload: dict[str, Any], identity: SecurityIdentity) -> tuple[XbrlFact, ...]:
        """Parsea con `edgartools` y traduce a nuestro tipo.

        El parseo es pesado (decenas de MB para una empresa grande) y síncrono:
        se llama desde un hilo para no bloquear el event loop.
        """
        from edgar.entity.parser import EntityFactsParser

        entity_facts = EntityFactsParser.parse_company_facts(payload)
        if entity_facts is None:
            raise EdgarUnavailableError(
                f"El payload de {identity.ticker} no tiene hechos XBRL utilizables."
            )
        converted = (to_xbrl_fact(fact) for fact in entity_facts.get_all_facts())
        return tuple(fact for fact in converted if fact is not None)
