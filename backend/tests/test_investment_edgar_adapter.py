"""Tests del adapter EDGAR (PHASE-44.6).

Sin red: los hechos son sintéticos y reproducen la forma real de `companyfacts`
—incluido el detalle que hace de esto algo no trivial: un 10-K arrastra dos o
tres columnas comparativas, y todas viajan con el `fy` del INFORME, no con el
suyo—.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.modules.investment.enums import AccountingStd
from app.modules.investment.fundamentals.adapters.annual import (
    build_raw_filings,
    filing_refs,
    restated_periods,
)
from app.modules.investment.fundamentals.adapters.base import SecurityIdentity, XbrlFact
from app.modules.investment.fundamentals.adapters.edgar import (
    EdgarAdapter,
    EdgarIdentityMissingError,
    EdgarUnavailableError,
    classify_sic,
    to_xbrl_fact,
)
from app.modules.investment.fundamentals.cache import FactsCache


def _fact(
    concept: str,
    value: object,
    *,
    end: date,
    start: date | None = None,
    accession: str = "0000063908-25-000012",
    filed: date = date(2025, 2, 20),
    fy: int = 2024,
    fp: str = "FY",
    form: str = "10-K",
    taxonomy: str = "us-gaap",
    unit: str = "USD",
) -> XbrlFact:
    return XbrlFact(
        taxonomy=taxonomy,
        concept=concept,
        value=Decimal(str(value)),
        unit=unit,
        period_end=end,
        period_start=start,
        form_type=form,
        fiscal_period=fp,
        fiscal_year=fy,
        accession=accession,
        filing_date=filed,
    )


def _year(concept: str, value: object, year: int, **kwargs: object) -> XbrlFact:
    """Un flujo anual completo del ejercicio `year`."""
    return _fact(
        concept,
        value,
        end=date(year, 12, 31),
        start=date(year, 1, 1),
        **kwargs,  # type: ignore[arg-type]
    )


# ── El anclaje por fecha de cierre ────────────────────────────────────


def test_las_comparativas_no_se_confunden_con_el_ejercicio_del_informe() -> None:
    """El corazón del asunto: en el 10-K de 2024 las tres columnas llevan
    `fy=2024`. Anclar por la etiqueta del informe metería el dato de 2022 en
    2024; anclar por la fecha de cierre lo pone donde va."""
    facts = [
        _year("Revenues", 25_920, 2024),
        _year("Revenues", 25_494, 2023),
        _year("Revenues", 23_183, 2022),
        # El balance de cada cierre, para que los tres ejercicios existan.
        _fact("Assets", 56_147, end=date(2024, 12, 31)),
        _fact("Assets", 56_435, end=date(2023, 12, 31)),
        _fact("Assets", 50_436, end=date(2022, 12, 31)),
    ]
    filings = build_raw_filings(facts)

    # Solo hay UN filing (un accession), así que solo su ejercicio principal sale.
    assert [f.fiscal_year_end for f in filings] == [date(2024, 12, 31)]
    assert filings[0].facts["us-gaap:Revenues"] == Decimal(25_920)


def test_cada_10k_aporta_su_propio_ejercicio() -> None:
    """Con tres informes salen tres ejercicios, cada uno con su cifra."""
    facts = []
    for year, accession in ((2022, "a-22"), (2023, "a-23"), (2024, "a-24")):
        filed = date(year + 1, 2, 20)
        facts += [
            _year("Revenues", year, year, accession=accession, filed=filed, fy=year),
            _fact(
                "Assets",
                year,
                end=date(year, 12, 31),
                accession=accession,
                filed=filed,
                fy=year,
            ),
        ]
    filings = build_raw_filings(facts)

    assert [f.fiscal_year for f in filings] == [2022, 2023, 2024]
    assert [f.fiscal_year_end for f in filings] == [
        date(2022, 12, 31),
        date(2023, 12, 31),
        date(2024, 12, 31),
    ]


def test_la_serie_sale_en_orden_ascendente() -> None:
    """`StatementSeries` lo exige, y llegan en el orden que quiera la SEC."""
    facts = []
    for year in (2024, 2022, 2023):
        facts += [
            _year("Revenues", year, year, accession=f"a-{year}", fy=year),
            _fact("Assets", year, end=date(year, 12, 31), accession=f"a-{year}", fy=year),
        ]
    assert [f.fiscal_year for f in build_raw_filings(facts)] == [2022, 2023, 2024]


def test_gana_la_vista_del_filing_mas_reciente() -> None:
    """Una reexpresión llega como comparativa del 10-K siguiente. La vista
    vigente es esa, no la cifra original."""
    facts = [
        _year("Revenues", 100, 2023, accession="a-23", filed=date(2024, 2, 20), fy=2023),
        _fact("Assets", 500, end=date(2023, 12, 31), accession="a-23", filed=date(2024, 2, 20)),
        # El 10-K de 2024 reexpresa 2023 a 95.
        _year("Revenues", 95, 2023, accession="a-24", filed=date(2025, 2, 20), fy=2024),
    ]
    filings = build_raw_filings(facts)
    year_2023 = next(f for f in filings if f.fiscal_year_end == date(2023, 12, 31))
    assert year_2023.facts["us-gaap:Revenues"] == Decimal(95)


def test_el_limite_se_queda_con_los_ejercicios_mas_recientes() -> None:
    """Recortar por el principio tiraría justo los años que interesan."""
    facts = []
    for year in range(2018, 2025):
        facts += [
            _year("Revenues", year, year, accession=f"a-{year}", fy=year),
            _fact("Assets", year, end=date(year, 12, 31), accession=f"a-{year}", fy=year),
        ]
    assert [f.fiscal_year for f in build_raw_filings(facts, limit=3)] == [2022, 2023, 2024]


# ── Qué es un dato anual ──────────────────────────────────────────────


def test_los_trimestres_no_entran() -> None:
    facts = [
        _fact(
            "Revenues",
            6_000,
            end=date(2024, 3, 31),
            start=date(2024, 1, 1),
            fp="Q1",
            form="10-Q",
        ),
        _fact("Assets", 100, end=date(2024, 12, 31)),
    ]
    filings = build_raw_filings(facts)
    assert "us-gaap:Revenues" not in filings[0].facts


def test_un_ytd_parcial_no_es_un_ejercicio() -> None:
    """Mismo cierre y mismo `fp=FY`, pero seis meses de duración: es un acumulado
    parcial que sumaría medio año como si fuera entero."""
    facts = [
        _fact("Revenues", 12_000, end=date(2024, 12, 31), start=date(2024, 7, 1)),
        _fact("Assets", 100, end=date(2024, 12, 31)),
    ]
    assert "us-gaap:Revenues" not in build_raw_filings(facts)[0].facts


def test_el_ano_fiscal_de_52_semanas_si_entra() -> None:
    """JNJ cierra el 28 de diciembre: 363 días. Un rango estrecho alrededor de
    365 dejaría fuera a media bolsa americana."""
    facts = [
        _fact(
            "Revenues",
            88_821,
            end=date(2024, 12, 29),
            start=date(2024, 1, 1),
        ),
        _fact("Assets", 180_104, end=date(2024, 12, 29)),
    ]
    filings = build_raw_filings(facts)
    assert filings[0].facts["us-gaap:Revenues"] == Decimal(88_821)


def test_un_hecho_posterior_al_cierre_no_desplaza_el_ejercicio() -> None:
    """Un 10-K puede traer un saldo posterior al cierre (deuda emitida en enero).
    Si ese saldo decidiera el fin de ejercicio saldría un año fantasma en enero
    sin ninguna otra partida anclada, y el ejercicio de verdad desaparecería."""
    facts = [
        _year("Revenues", 25_920, 2024),
        _fact("Assets", 56_147, end=date(2024, 12, 31)),
        _fact("LongTermDebtNoncurrent", 9_000, end=date(2025, 1, 15)),
    ]
    filings = build_raw_filings(facts)

    assert [f.fiscal_year_end for f in filings] == [date(2024, 12, 31)]
    assert filings[0].facts["us-gaap:Assets"] == Decimal(56_147)
    assert "us-gaap:LongTermDebtNoncurrent" not in filings[0].facts


def test_los_ratios_por_accion_no_entran() -> None:
    """Un beneficio por acción de 2,3 $ en la misma clave que un importe daría un
    'resultado' de 2,3 dólares."""
    facts = [
        _fact("EarningsPerShareBasic", "2.3", end=date(2024, 12, 31), unit="USD/shares"),
        _fact("Assets", 100, end=date(2024, 12, 31)),
    ]
    assert "us-gaap:EarningsPerShareBasic" not in build_raw_filings(facts)[0].facts


# ── La portada (`dei`) ────────────────────────────────────────────────


def test_la_portada_se_atribuye_por_filing_no_por_fecha() -> None:
    """Su fecha es la de cubierta, POSTERIOR al cierre: anclarla por fecha la
    dejaría siempre fuera."""
    facts = [
        _fact("Assets", 56_147, end=date(2024, 12, 31)),
        _fact(
            "EntityCommonStockSharesOutstanding",
            712_000_000,
            end=date(2025, 2, 12),
            taxonomy="dei",
            unit="shares",
        ),
    ]
    filings = build_raw_filings(facts)
    assert filings[0].facts["dei:EntityCommonStockSharesOutstanding"] == Decimal(712_000_000)


def test_la_portada_de_un_filing_no_contamina_otro_ejercicio() -> None:
    """Cada portada va al ejercicio del que su 10-K es informe principal."""
    facts = [
        _fact("Assets", 1, end=date(2023, 12, 31), accession="a-23", filed=date(2024, 2, 1)),
        _fact(
            "EntityCommonStockSharesOutstanding",
            700,
            end=date(2024, 2, 1),
            taxonomy="dei",
            unit="shares",
            accession="a-23",
            filed=date(2024, 2, 1),
        ),
        _fact("Assets", 2, end=date(2024, 12, 31), accession="a-24", filed=date(2025, 2, 1)),
        _fact(
            "EntityCommonStockSharesOutstanding",
            650,
            end=date(2025, 2, 1),
            taxonomy="dei",
            unit="shares",
            accession="a-24",
            filed=date(2025, 2, 1),
        ),
    ]
    by_year = {f.fiscal_year_end: f for f in build_raw_filings(facts)}
    assert by_year[date(2023, 12, 31)].facts["dei:EntityCommonStockSharesOutstanding"] == Decimal(
        700
    )
    assert by_year[date(2024, 12, 31)].facts["dei:EntityCommonStockSharesOutstanding"] == Decimal(
        650
    )


# ── Metadatos del ejercicio ───────────────────────────────────────────


def test_la_divisa_se_lee_de_las_unidades() -> None:
    """Un 'USD' por defecto convertiría una cifra en euros en una cifra en
    dólares sin que nadie se entere."""
    facts = [
        _fact("Assets", 1_000, end=date(2024, 12, 31), unit="EUR"),
        _fact("Liabilities", 400, end=date(2024, 12, 31), unit="EUR"),
    ]
    assert build_raw_filings(facts)[0].currency == "EUR"


def test_sin_unidades_reconocibles_la_divisa_es_dolar() -> None:
    facts = [_fact("Assets", 1_000, end=date(2024, 12, 31), unit="")]
    assert build_raw_filings(facts)[0].currency == "USD"


def test_la_norma_contable_viaja_al_ejercicio() -> None:
    facts = [_fact("Assets", 1_000, end=date(2024, 12, 31))]
    filings = build_raw_filings(facts, accounting_std=AccountingStd.IFRS)
    assert filings[0].accounting_std is AccountingStd.IFRS


def test_los_filings_salen_del_mas_reciente_al_mas_antiguo() -> None:
    facts = []
    for year in (2023, 2024):
        facts.append(_fact("Assets", year, end=date(year, 12, 31), accession=f"a-{year}", fy=year))
    refs = filing_refs(facts)
    assert [ref.fiscal_year for ref in refs] == [2024, 2023]
    assert refs[0].accession == "a-2024"


def test_solo_se_senalan_los_ejercicios_con_mas_de_un_filing() -> None:
    """Un ejercicio con un solo informe no puede haber sido reexpresado."""
    facts = [
        _year("Revenues", 100, 2023, accession="a-23", filed=date(2024, 2, 20)),
        _year("Revenues", 95, 2023, accession="a-24", filed=date(2025, 2, 20)),
        _year("Revenues", 120, 2024, accession="a-24", filed=date(2025, 2, 20)),
    ]
    señalados = restated_periods(facts)
    assert list(señalados) == [date(2023, 12, 31)]
    assert señalados[date(2023, 12, 31)] == ("a-23", "a-24")


# ── Conversión desde el modelo de la librería ─────────────────────────


class _LibFact:
    """Lo justo de `FinancialFact` que consume el adapter."""

    def __init__(self, **kwargs: object) -> None:
        defaults: dict[str, object] = {
            "taxonomy": "us-gaap",
            "concept": "Assets",
            "value": 56_147_000_000,
            "unit": "USD",
            "period_end": date(2024, 12, 31),
            "period_start": None,
            "form_type": "10-K",
            "fiscal_period": "FY",
            "fiscal_year": 2024,
            "accession": "0000063908-25-000012",
            "filing_date": date(2025, 2, 20),
        }
        defaults.update(kwargs)
        for name, value in defaults.items():
            setattr(self, name, value)


def test_el_importe_se_convierte_sin_pasar_por_float() -> None:
    """`numeric_value` de la librería es un `float`. Convertir desde el valor
    original mantiene exacta una cifra de once dígitos que luego se resta."""
    fact = to_xbrl_fact(_LibFact(value=56_147_000_000))
    assert fact is not None
    assert fact.value == Decimal("56147000000")


def test_un_hecho_de_texto_no_es_un_importe() -> None:
    assert to_xbrl_fact(_LibFact(value=["no", "numérico"])) is None


def test_un_hecho_sin_fecha_de_cierre_se_descarta() -> None:
    assert to_xbrl_fact(_LibFact(period_end=None)) is None


def test_la_clave_lleva_el_namespace() -> None:
    fact = to_xbrl_fact(_LibFact(taxonomy="dei", concept="EntityCommonStockSharesOutstanding"))
    assert fact is not None
    assert fact.key == "dei:EntityCommonStockSharesOutstanding"


# ── Identidad y clasificación ─────────────────────────────────────────


async def test_sin_identidad_falla_al_salir_a_la_red(tmp_path: Path) -> None:
    """El error llega con un mensaje accionable, no con un 403 de la SEC a mitad
    de la ingesta — ni con la librería pidiéndola por consola, que en un backend
    es una petición colgada contra un stdin que nadie va a rellenar."""
    adapter = EdgarAdapter(identity="   ", cache_dir=tmp_path)
    with pytest.raises(EdgarIdentityMissingError):
        await adapter.resolve("MCD")


async def test_con_la_cache_poblada_no_hace_falta_identidad(tmp_path: Path) -> None:
    """Guardar el crudo sirve justo para esto: reingerir tras cambiar el mapeo,
    montar fixtures o reproducir un análisis viejo, todo sin tocar la SEC."""
    adapter = EdgarAdapter(identity="", cache_dir=tmp_path)
    adapter.cache.store("63908", json.dumps(_companyfacts()).encode())

    identity = SecurityIdentity(ticker="MCD", cik="0000063908", name="MCDONALDS CORP")
    facts = await adapter.fetch_facts(identity)

    assert facts
    assert any(fact.key == "us-gaap:Assets" for fact in facts)


@pytest.mark.parametrize(
    ("sic", "esperado"),
    [
        ("6798", (True, True)),  # REIT (y 67xx es holding financiero)
        ("5812", (False, False)),  # restauración — MCD
        ("2834", (False, False)),  # farmacia — JNJ
        ("6021", (False, True)),  # banca comercial
        (None, (False, False)),
    ],
)
def test_el_sic_decide_que_modelos_aplican(sic: str | None, esperado: tuple[bool, bool]) -> None:
    """Marcar de más apaga los forenses en una empresa normal; marcar de menos
    los corre en un banco y devuelve números sin significado."""
    assert classify_sic(sic) == esperado


class _FakeCompany:
    """Lo justo de `edgar.Company` que lee `resolve`. La clave es que
    `is_financial_institution` sea un MÉTODO, como en la librería real."""

    def __init__(
        self,
        *,
        cik: int,
        name: str,
        sic: str | None,
        financial: bool,
        reit_subtype: str | None,
    ) -> None:
        self.cik = cik
        self.name = name
        self.sic = sic
        self.reit_subtype = reit_subtype
        self._financial = financial

    def is_financial_institution(self) -> bool:  # un MÉTODO, no un atributo: esa es la trampa
        return self._financial


async def test_una_empresa_normal_no_sale_financiera(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`is_financial_institution` es un método en edgartools. Leerlo con getattr
    sin llamarlo devuelve el objeto método —truthy— y marcaría a MCD (SIC 5812,
    restauración) como financiera, apagándole los forenses. La regresión: aunque
    el método devuelva False, la empresa NO debe salir financiera."""
    adapter = EdgarAdapter(identity="Tester tester@example.com", cache_dir=tmp_path)
    company = _FakeCompany(
        cik=63908, name="MCDONALDS CORP", sic="5812", financial=False, reit_subtype=None
    )
    monkeypatch.setattr(adapter, "_load_company", lambda ticker: company)

    identity = await adapter.resolve("MCD")

    assert identity.is_financial is False
    assert identity.is_reit is False
    assert identity.sic == "5812"


async def test_un_ticker_que_la_sec_no_conoce_se_traduce_a_error_de_dominio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un ticker inexistente NO devuelve un objeto vacío: la librería lanza
    `CompanyNotFoundError` desde el constructor. Sin traducirla subía sin capturar
    y el endpoint respondía **500** aunque su docstring promete 404 — el usuario
    recibía "error interno" por escribir mal un ticker.

    Se lanza la excepción REAL de `edgartools`, no un doble: si una versión futura
    la renombra o cambia su jerarquía, este test lo caza en CI en vez de que el
    500 vuelva en producción (PHASE-44.6).
    """
    from edgar import CompanyNotFoundError

    def _boom(_ticker: str) -> object:
        raise CompanyNotFoundError("NOSUCHTICKER")

    # `_load_company` importa `Company` DENTRO de la función, así que parchear el
    # atributo del paquete es lo que ve el código en tiempo de llamada.
    monkeypatch.setattr("edgar.Company", _boom)

    adapter = EdgarAdapter(identity="Tester tester@example.com", cache_dir=tmp_path)
    with pytest.raises(EdgarUnavailableError) as excinfo:
        await adapter.resolve("NOSUCHTICKER")

    assert "NOSUCHTICKER" in str(excinfo.value)


async def test_el_override_de_la_libreria_sigue_marcando_al_banco(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El fix no puede pasarse de frenada: si el método SÍ devuelve True (o hay
    `reit_subtype`), esos overrides deben seguir aplicando por encima del SIC."""
    adapter = EdgarAdapter(identity="Tester tester@example.com", cache_dir=tmp_path)
    # SIC desconocido: sin el override, ni REIT ni financiera; con él, ambas.
    company = _FakeCompany(
        cik=726728, name="REALTY INCOME CORP", sic=None, financial=True, reit_subtype="equity"
    )
    monkeypatch.setattr(adapter, "_load_company", lambda ticker: company)

    identity = await adapter.resolve("O")

    assert identity.is_financial is True
    assert identity.is_reit is True


# ── Cache ─────────────────────────────────────────────────────────────


def test_la_cache_devuelve_lo_que_guardo(tmp_path: Path) -> None:
    cache = FactsCache(tmp_path)
    cache.store("63908", json.dumps({"entityName": "MCDONALDS CORP"}).encode())
    assert cache.path_for("63908").name == "CIK0000063908.json"
    payload = cache.load(63908)
    assert payload is not None
    assert payload["entityName"] == "MCDONALDS CORP"


def test_una_cache_vacia_no_es_un_error(tmp_path: Path) -> None:
    assert FactsCache(tmp_path).load("63908") is None


def test_un_payload_corrupto_se_trata_como_ausencia(tmp_path: Path) -> None:
    """Una descarga cortada a medias es recuperable volviendo a descargar;
    devolver medio payload haría que el fallo apareciese mucho más lejos, ya
    convertido en huecos raros."""
    cache = FactsCache(tmp_path)
    cache.store("63908", b'{"entityName": "MCDONALD')
    assert cache.load("63908") is None


def test_la_escritura_no_deja_ficheros_a_medias(tmp_path: Path) -> None:
    """El temporal no debe sobrevivir a una escritura correcta."""
    cache = FactsCache(tmp_path)
    cache.store("63908", b"{}")
    assert [p.name for p in tmp_path.iterdir()] == ["CIK0000063908.json"]


# ── El contrato con la librería ───────────────────────────────────────


def _datapoint(value: object, *, end: str, start: str | None = None) -> dict[str, object]:
    point: dict[str, object] = {
        "end": end,
        "val": value,
        "accn": "0000063908-25-000012",
        "fy": 2024,
        "fp": "FY",
        "form": "10-K",
        "filed": "2025-02-20",
    }
    if start is not None:
        point["start"] = start
    return point


def _companyfacts() -> dict[str, object]:
    """Un `companyfacts` con la forma real de la SEC, al estilo de MCD."""
    year = {"end": "2024-12-31", "start": "2024-01-01"}
    return {
        "cik": 63908,
        "entityName": "MCDONALDS CORP",
        "facts": {
            "us-gaap": {
                "Assets": {"units": {"USD": [_datapoint(56_147_000_000, end="2024-12-31")]}},
                "StockholdersEquity": {
                    "units": {"USD": [_datapoint(-3_797_000_000, end="2024-12-31")]}
                },
                "Revenues": {"units": {"USD": [_datapoint(25_920_000_000, **year)]}},  # type: ignore[arg-type]
                "OperatingIncomeLoss": {
                    "units": {"USD": [_datapoint(12_393_000_000, **year)]}  # type: ignore[arg-type]
                },
                "NetIncomeLoss": {"units": {"USD": [_datapoint(8_223_000_000, **year)]}},  # type: ignore[arg-type]
                "IncomeTaxExpenseBenefit": {
                    "units": {"USD": [_datapoint(2_190_000_000, **year)]}  # type: ignore[arg-type]
                },
                "InterestExpense": {"units": {"USD": [_datapoint(1_360_000_000, **year)]}},  # type: ignore[arg-type]
                "EarningsPerShareBasic": {
                    "units": {"USD/shares": [_datapoint(11.39, **year)]}  # type: ignore[arg-type]
                },
            },
            "dei": {
                "EntityCommonStockSharesOutstanding": {
                    "units": {"shares": [_datapoint(712_000_000, end="2025-02-12")]}
                }
            },
        },
    }


def test_el_pipeline_completo_desde_un_payload_de_la_sec() -> None:
    """De JSON crudo de la SEC a estado canónico, pasando por el parser REAL de
    la librería.

    Es el test que fija el contrato con `edgartools`, y hace falta porque su
    modelo tiene una trampa silenciosa: devuelve el concepto ya cualificado
    (`'us-gaap:Assets'`) mientras expone `taxonomy` por separado. Volver a
    componerlo daría `'us-gaap:us-gaap:Assets'`, ninguna partida encontraría su
    concepto y el resultado no sería un error sino una empresa entera en blanco.
    """
    from edgar.entity.parser import EntityFactsParser

    from app.modules.investment.fundamentals.normalization import normalize

    entity_facts = EntityFactsParser.parse_company_facts(_companyfacts())
    assert entity_facts is not None

    facts = [f for f in (to_xbrl_fact(raw) for raw in entity_facts.get_all_facts()) if f]
    filings = build_raw_filings(facts)
    assert len(filings) == 1

    statement = normalize(filings[0])
    assert statement.total_assets == Decimal(56_147_000_000)
    assert statement.equity == Decimal(-3_797_000_000)
    assert statement.revenue == Decimal(25_920_000_000)
    assert statement.ebit == Decimal(12_393_000_000)
    assert statement.shares_outstanding_eop == Decimal(712_000_000)
    # MCD no publica `Liabilities`: sale de activo − patrimonio.
    assert statement.total_liabilities == Decimal(59_944_000_000)
    # Y el beneficio por acción no se ha colado como si fuera un importe.
    assert all("EarningsPerShare" not in key for key in filings[0].facts)


def test_el_concepto_llega_sin_duplicar_el_namespace() -> None:
    fact = to_xbrl_fact(_LibFact(taxonomy="us-gaap", concept="us-gaap:Assets"))
    assert fact is not None
    assert fact.concept == "Assets"
    assert fact.key == "us-gaap:Assets"
