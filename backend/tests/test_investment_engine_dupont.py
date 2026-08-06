"""Las métricas de PHASE-44.10: DuPont extendido, S7 y S8.

El grueso de este fichero prueba UNA cosa: que la identidad de cinco factores
**cierra**. No es ceremonia — es el requisito que decidió qué EBIT usar.

La identidad es:

    ROE = margen operativo × efecto fiscal × coste financiero × rotación × apalancamiento

        BN        EBIT     BN      BAI     Ventas    Activo
    ────────── = ────── × ───── × ────── × ─────── × ──────────
    Patrimonio   Ventas    BAI    EBIT     Activo   Patrimonio

El EBIT sólo se cancela si el margen operativo y el coste financiero usan **el
mismo**. El motor tiene dos (`ebit` reportado y `ebit_clean`, limpio de
deterioros y plusvalías), así que elegir mal no lanza ningún error: simplemente
infla el ROE reconstruido por el factor `limpio/reportado`, y sólo en los años
con deterioros — que son justo los años en los que uno mira el DuPont.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.modules.investment.analysis.engine import base_ratios
from app.modules.investment.analysis.engine.base_ratios import BaseRatiosResult
from app.modules.investment.analysis.engine.types import SecuritySnapshot, StatementSeries
from app.modules.investment.enums import AccountingStd, SectorInternal
from app.modules.investment.fundamentals.canonical import CanonicalStatement


def dec(value: str | int) -> Decimal:
    return Decimal(value)


TOLERANCE = Decimal("1e-20")
"""Los factores son cocientes de `Decimal` con decimal periódico, así que el
producto arrastra ~1e-28 de redondeo. Cualquier residuo mayor es un fallo de
fórmula, no de precisión."""


# ── Empresa con deterioros: la que destapa la trampa ──────────────────
#
# Ventas 1.000 · EBIT reportado 200 · deterioros 30 · plusvalías 10
#   → EBIT limpio = 200 + 30 − 10 = 220   (¡distinto del reportado!)
# Intereses 40 · BAI 160 · impuestos 40 · BN 120
# Activo 800 en los dos años (media = 800) · patrimonio 400 (media = 400)
#   → ROE = 120 / 400 = 0,30


def _year(fiscal_year: int) -> CanonicalStatement:
    return CanonicalStatement(
        fiscal_year=fiscal_year,
        fiscal_year_end=date(fiscal_year, 12, 31),
        accounting_std=AccountingStd.GAAP,
        cash=dec(100),
        receivables=dec(150),
        inventory=dec(150),
        current_assets=dec(400),
        total_assets=dec(800),
        short_term_debt=dec(60),
        ltd_current_portion=dec(40),
        accounts_payable=dec(100),
        current_liabilities=dec(200),
        long_term_debt=dec(200),
        total_liabilities=dec(400),
        equity=dec(400),
        revenue=dec(1000),
        cogs=dec(600),
        depreciation_amortization=dec(50),
        impairments=dec(30),
        gains_on_sale_of_business=dec(10),
        ebit=dec(200),
        interest_expense=dec(40),
        pretax_income=dec(160),
        taxes=dec(40),
        net_income=dec(120),
        shares_basic=dec(100),
        cfo=dec(180),
        capex=dec(70),
        dividends_paid=dec(40),
        taxes_paid=dec(40),
    )


@pytest.fixture
def result() -> BaseRatiosResult:
    series = StatementSeries(
        security=SecuritySnapshot(
            ticker="DUP",
            sector=SectorInternal.INDUSTRIALS,
            accounting_std=AccountingStd.GAAP,
        ),
        statements=(_year(2023), _year(2024)),
        as_of=date(2025, 3, 31),
    )
    return base_ratios.compute(series)


def _dupont(result: BaseRatiosResult, year: int = 2024) -> base_ratios.DuPontDecomposition:
    point = next(d for d in result.dupont if d.fiscal_year == year)
    return point


# ── La identidad ──────────────────────────────────────────────────────


def test_los_cinco_factores_valen_lo_esperado(result: BaseRatiosResult) -> None:
    """Cada factor, calculado a mano sobre el sintético."""
    d = _dupont(result)
    assert d.operating_margin.value == dec("0.2"), "EBIT reportado 200 / ventas 1.000"
    assert d.tax_effect.value == dec("0.75"), "BN 120 / BAI 160"
    assert d.financial_cost.value == dec("0.8"), "BAI 160 / EBIT reportado 200"
    assert d.asset_turnover.value == dec("1.25"), "ventas 1.000 / activo medio 800"
    assert d.equity_multiplier.value == dec("2"), "activo medio 800 / patrimonio medio 400"


def test_la_identidad_de_cinco_factores_cierra(result: BaseRatiosResult) -> None:
    """0,20 × 0,75 × 0,80 × 1,25 × 2,00 = 0,30 = ROE."""
    d = _dupont(result)
    assert d.check_five is not None
    assert abs(d.check_five) < TOLERANCE, f"la identidad no cierra: {d.check_five}"


def test_la_identidad_de_tres_factores_cierra(result: BaseRatiosResult) -> None:
    d = _dupont(result)
    assert d.check_three is not None
    assert abs(d.check_three) < TOLERANCE


def test_usar_el_ebit_limpio_en_el_margen_operativo_rompe_la_identidad(
    result: BaseRatiosResult,
) -> None:
    """La regresión que este diseño evita, cuantificada.

    Si el margen operativo usara `ebit_clean` (220) mientras el coste financiero
    usa el reportado (200), el EBIT no se cancela y el ROE reconstruido sale
    inflado por 220/200 = 1,10 — un 10% de ROE inventado, en silencio y sólo en
    los años con deterioros. Sobre datos reales de JNJ el error llegaba a 4
    puntos porcentuales de ROE.
    """
    d = _dupont(result)
    roe = result.get("R5", 2024)
    assert roe is not None and roe.value is not None
    ebit_clean_margin = dec("220") / dec("1000")

    reconstruido = ebit_clean_margin * dec("0.75") * dec("0.8") * dec("1.25") * dec("2")
    assert reconstruido != roe.value
    assert reconstruido - roe.value == dec("0.03"), "3 puntos de ROE inventados"
    # Y con el reportado, cierra:
    assert d.check_five is not None and abs(d.check_five) < TOLERANCE


def test_un_factor_ausente_deja_el_cuadre_no_verificable() -> None:
    """`None` no es «cuadra»: es «no se ha podido comprobar».

    Misma regla que el cuadre del balance en la ingesta — un check que no se
    puede evaluar jamás se reporta como superado (PHASE-44.6).
    """
    sin_ebit = _year(2024)
    serie = StatementSeries(
        security=SecuritySnapshot("X", SectorInternal.INDUSTRIALS, AccountingStd.GAAP),
        statements=(
            _year(2023),
            CanonicalStatement(
                **{
                    **{
                        f.name: getattr(sin_ebit, f.name)
                        for f in sin_ebit.__dataclass_fields__.values()
                    },
                    "ebit": None,
                }
            ),
        ),
        as_of=date(2025, 3, 31),
    )
    d = next(p for p in base_ratios.compute(serie).dupont if p.fiscal_year == 2024)
    assert d.operating_margin.status == "not_computable"
    assert d.check_five is None, "sin margen operativo el cuadre no es verificable"


def test_con_patrimonio_negativo_no_hay_cuadre_que_verificar() -> None:
    """Le pasa a McDonald's de verdad: patrimonio neto negativo.

    El ROE y el apalancamiento salen `not_computable` (guarda de denominador
    positivo), así que la identidad no se puede comprobar — y se dice.
    """
    base = _year(2024)
    negativo = CanonicalStatement(
        **{
            **{f.name: getattr(base, f.name) for f in base.__dataclass_fields__.values()},
            "equity": dec(-100),
            "total_liabilities": dec(900),
        }
    )
    serie = StatementSeries(
        security=SecuritySnapshot("MCD", SectorInternal.CONSUMER_DISCRETIONARY, AccountingStd.GAAP),
        statements=(negativo,),
        as_of=date(2025, 3, 31),
    )
    result = base_ratios.compute(serie)
    d = _dupont(result)
    assert d.equity_multiplier.status == "not_computable"
    assert d.check_five is None and d.check_three is None


def test_el_efecto_fiscal_se_calcula_aunque_el_resultado_sea_negativo() -> None:
    """Con BAI negativo la identidad SIGUE cerrando (los signos se cancelan).

    Bloquearlo rompería la descomposición de un año en pérdidas, que es justo
    cuando interesa mirarla. El factor se vuelve difícil de leer, no inválido.
    """
    base = _year(2024)
    perdidas = CanonicalStatement(
        **{
            **{f.name: getattr(base, f.name) for f in base.__dataclass_fields__.values()},
            "pretax_income": dec(-160),
            "net_income": dec(-120),
            "taxes": dec(-40),
        }
    )
    serie = StatementSeries(
        security=SecuritySnapshot("X", SectorInternal.INDUSTRIALS, AccountingStd.GAAP),
        statements=(perdidas,),
        as_of=date(2025, 3, 31),
    )
    d = _dupont(base_ratios.compute(serie))
    assert d.tax_effect.value == dec("0.75"), "(−120) / (−160)"
    assert d.financial_cost.value == dec("-0.8"), "(−160) / 200"
    assert d.check_five is not None and abs(d.check_five) < TOLERANCE


# ── S7 · Ratio de endeudamiento ───────────────────────────────────────


def test_s7_endeudamiento(result: BaseRatiosResult) -> None:
    """Pasivo 400 / patrimonio 400 = 1,0 → dentro de la banda sana."""
    metric = result.get("S7", 2024)
    assert metric is not None
    assert metric.value == dec("1")
    assert metric.band == "healthy"


@pytest.mark.parametrize(
    ("liabilities", "expected_band", "por_que"),
    [
        (dec(200), "caution", "0,5× — poca deuda avisa, pero NO es riesgo"),
        (dec(400), "healthy", "1,0× — borde inferior de la banda sana"),
        (dec(800), "healthy", "2,0× — borde superior"),
        (dec(1000), "caution", "2,5× — por encima del óptimo"),
        (dec(1400), "stressed", "3,5× — pasa el corte rojo"),
    ],
)
def test_s7_banda_central(liabilities: Decimal, expected_band: str, por_que: str) -> None:
    base = _year(2024)
    statement = CanonicalStatement(
        **{
            **{f.name: getattr(base, f.name) for f in base.__dataclass_fields__.values()},
            "total_liabilities": liabilities,
        }
    )
    serie = StatementSeries(
        security=SecuritySnapshot("X", SectorInternal.INDUSTRIALS, AccountingStd.GAAP),
        statements=(statement,),
        as_of=date(2025, 3, 31),
    )
    metric = base_ratios.compute(serie).get("S7", 2024)
    assert metric is not None
    assert metric.band == expected_band, por_que


def test_s7_con_patrimonio_negativo_no_se_calcula() -> None:
    """Con patrimonio negativo el cociente sale POSITIVO y parece sano justo en
    la empresa más frágil. Se reporta como no calculable, con la razón."""
    base = _year(2024)
    statement = CanonicalStatement(
        **{
            **{f.name: getattr(base, f.name) for f in base.__dataclass_fields__.values()},
            "equity": dec(-100),
        }
    )
    serie = StatementSeries(
        security=SecuritySnapshot("X", SectorInternal.INDUSTRIALS, AccountingStd.GAAP),
        statements=(statement,),
        as_of=date(2025, 3, 31),
    )
    metric = base_ratios.compute(serie).get("S7", 2024)
    assert metric is not None
    assert metric.status == "not_computable"
    assert metric.reason is not None and "patrimonio neto" in metric.reason


# ── S8 · Calidad de la deuda ──────────────────────────────────────────


def test_s8_calidad_de_la_deuda(result: BaseRatiosResult) -> None:
    """(60 + 40) / (60 + 40 + 200) = 100/300 = 33,3% → sano (≤ 40%)."""
    metric = result.get("S8", 2024)
    assert metric is not None
    assert metric.value is not None
    assert metric.value.quantize(dec("0.0001")) == dec("0.3333")
    assert metric.band == "healthy"


def test_s8_sin_deuda_no_hay_calidad_que_medir() -> None:
    """Una empresa sin deuda no tiene una calidad de deuda del 0%: no tiene
    deuda. Sale no calculable con «denominador cero», que es la verdad."""
    base = _year(2024)
    sin_deuda = CanonicalStatement(
        **{
            **{f.name: getattr(base, f.name) for f in base.__dataclass_fields__.values()},
            "short_term_debt": dec(0),
            "ltd_current_portion": dec(0),
            "long_term_debt": dec(0),
        }
    )
    serie = StatementSeries(
        security=SecuritySnapshot("X", SectorInternal.INDUSTRIALS, AccountingStd.GAAP),
        statements=(sin_deuda,),
        as_of=date(2025, 3, 31),
    )
    metric = base_ratios.compute(serie).get("S8", 2024)
    assert metric is not None
    assert metric.status == "not_computable"
    assert metric.reason is not None and "deuda total" in metric.reason


def test_s8_toda_la_deuda_a_corto_es_rojo() -> None:
    base = _year(2024)
    todo_corto = CanonicalStatement(
        **{
            **{f.name: getattr(base, f.name) for f in base.__dataclass_fields__.values()},
            "short_term_debt": dec(300),
            "ltd_current_portion": dec(0),
            "long_term_debt": dec(0),
        }
    )
    serie = StatementSeries(
        security=SecuritySnapshot("X", SectorInternal.INDUSTRIALS, AccountingStd.GAAP),
        statements=(todo_corto,),
        as_of=date(2025, 3, 31),
    )
    metric = base_ratios.compute(serie).get("S8", 2024)
    assert metric is not None
    assert metric.value == dec(1)
    assert metric.band == "stressed"
