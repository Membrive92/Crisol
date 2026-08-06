"""Múltiplos de valoración (PHASE-44.12) — capa pura.

Las cifras son las REALES de McDonald's FY2025, consultadas en la base tras
corregir el bug de escala de acciones. Con precio 298,40 USD, los valores que
salen aquí son los que verá el usuario en pantalla.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.modules.investment.analysis.engine.types import SecuritySnapshot, StatementSeries
from app.modules.investment.analysis.engine.valuation import (
    METRIC_CATALOG,
    ValuationInputs,
    compute_valuation,
)
from app.modules.investment.enums import AccountingStd, SectorInternal
from app.modules.investment.fundamentals.canonical import CanonicalStatement

_PRICE = Decimal("298.40")
_TODAY = date(2026, 8, 6)


def _mcd_2025(**overrides: object) -> CanonicalStatement:
    """MCD FY2025 real. `equity` es NEGATIVO: -1.791 M$, por autocartera."""
    base: dict[str, object] = {
        "fiscal_year": 2025,
        "fiscal_year_end": date(2025, 12, 31),
        "accounting_std": AccountingStd.GAAP,
        "currency": "USD",
        "filing_accession": "0000063908-26-000035",
        "item_provenance": {},
        "raw_source_ref": {},
        "revenue": Decimal("26885000000"),
        "net_income": Decimal("8563000000"),
        "equity": Decimal("-1791000000"),
        "cfo": Decimal("10551000000"),
        "capex": Decimal("3365000000"),
        "ebit": Decimal("12393000000"),
        "depreciation_amortization": Decimal("457000000"),
        "short_term_debt": Decimal("798000000"),
        "ltd_current_portion": Decimal("725000000"),
        "long_term_debt": Decimal("39973000000"),
        "cash": Decimal("774000000"),
        "current_financial_assets": Decimal("0"),
        "shares_outstanding_eop": Decimal("710398642"),
    }
    base.update(overrides)
    return CanonicalStatement(**base)  # type: ignore[arg-type]


def _series(statement: CanonicalStatement | None, *, is_financial: bool = False) -> StatementSeries:
    return StatementSeries(
        security=SecuritySnapshot(
            ticker="MCD",
            sector=SectorInternal.CONSUMER_DISCRETIONARY,
            accounting_std=AccountingStd.GAAP,
            is_financial=is_financial,
        ),
        statements=(statement,) if statement is not None else (),
        as_of=_TODAY,
    )


def _inputs(**overrides: object) -> ValuationInputs:
    base: dict[str, object] = {
        "price": _PRICE,
        "quote_as_of": _TODAY,
        "quote_currency": "USD",
    }
    base.update(overrides)
    return ValuationInputs(**base)  # type: ignore[arg-type]


def _by_key(result: object) -> dict[str, object]:
    return {m.key: m for m in result.metrics}  # type: ignore[attr-defined]


# ── Los números ───────────────────────────────────────────────────────


def test_capitalizacion_unica_para_todos() -> None:
    """298,40 × 710.398.642 = 211.982.954.772,80. Decisión del usuario: un solo
    denominador de acciones, para que «capitalización» signifique lo mismo en
    los cinco múltiplos."""
    result = compute_valuation(_series(_mcd_2025()), _inputs())
    assert result.market_cap == Decimal("211982954772.80")


def test_per_con_datos_reales() -> None:
    result = compute_valuation(_series(_mcd_2025()), _inputs())
    per = _by_key(result)["V1"]
    assert per.status == "ok"  # type: ignore[attr-defined]
    assert round(per.value, 2) == Decimal("24.76")  # type: ignore[attr-defined]


def test_precio_ventas_y_precio_caja_libre() -> None:
    metrics = _by_key(compute_valuation(_series(_mcd_2025()), _inputs()))
    assert round(metrics["V2"].value, 2) == Decimal("7.88")  # type: ignore[attr-defined]
    # caja libre = 10.551 − 3.365 = 7.186 M$
    assert round(metrics["V4"].value, 2) == Decimal("29.50")  # type: ignore[attr-defined]


def test_ev_ebitda_con_deuda_neta_real() -> None:
    """EV = 211.983 + 40.722 = 252.705 M$; EBITDA = 12.393 + 457 = 12.850 M$."""
    result = compute_valuation(_series(_mcd_2025()), _inputs())
    assert result.enterprise_value == Decimal("252704954772.80")
    assert round(_by_key(result)["V5"].value, 2) == Decimal("19.67")  # type: ignore[attr-defined]


# ── El patrimonio negativo de MCD ─────────────────────────────────────


def test_precio_valor_contable_no_computable_con_patrimonio_negativo() -> None:
    """MCD tiene patrimonio NEGATIVO por años de recompras. Un P/VC de −118×
    se leería como 'baratísimo' cuando no significa nada."""
    metrics = _by_key(compute_valuation(_series(_mcd_2025()), _inputs()))
    v3 = metrics["V3"]
    assert v3.status == "not_computable"  # type: ignore[attr-defined]
    assert v3.value is None  # type: ignore[attr-defined]
    assert "patrimonio neto" in (v3.reason or "")  # type: ignore[attr-defined]


def test_el_valor_contable_por_accion_si_se_emite_aunque_sea_negativo() -> None:
    """Aquí el signo INFORMA en vez de engañar: −2,52 $/acción dice algo cierto
    sobre la estructura de capital. Es la asimetría deliberada con V3."""
    v6 = _by_key(compute_valuation(_series(_mcd_2025()), _inputs()))["V6"]
    assert v6.status == "ok"  # type: ignore[attr-defined]
    assert round(v6.value, 2) == Decimal("-2.52")  # type: ignore[attr-defined]


def test_rentabilidad_caja_libre_no_es_el_reciproco_de_v4() -> None:
    """V7 se emite sin guard: con caja libre negativa diría 'quema caja' en vez
    de desaparecer, que es lo que le pasaría a V4."""
    metrics = _by_key(compute_valuation(_series(_mcd_2025()), _inputs()))
    assert round(metrics["V7"].value * 100, 2) == Decimal("3.39")  # type: ignore[attr-defined]

    quema = _by_key(
        compute_valuation(
            _series(_mcd_2025(cfo=Decimal("1000000000"), capex=Decimal("3365000000"))), _inputs()
        )
    )
    assert quema["V4"].status == "not_computable"  # type: ignore[attr-defined]
    assert quema["V7"].value < 0  # type: ignore[attr-defined]


# ── Casos límite ──────────────────────────────────────────────────────


def test_beneficio_negativo_no_produce_un_per_barato() -> None:
    metrics = _by_key(
        compute_valuation(_series(_mcd_2025(net_income=Decimal("-500000000"))), _inputs())
    )
    assert metrics["V1"].status == "not_computable"  # type: ignore[attr-defined]


def test_caja_neta_mayor_que_la_capitalizacion_anula_ev_ebitda() -> None:
    """`divide` no mira el numerador, así que este caso hay que interceptarlo
    antes o saldría un EV/EBITDA negativo que se lee como 'regalado'."""
    result = compute_valuation(
        _series(
            _mcd_2025(
                cash=Decimal("300000000000"),
                short_term_debt=Decimal("0"),
                ltd_current_portion=Decimal("0"),
                long_term_debt=Decimal("0"),
            )
        ),
        _inputs(),
    )
    v5 = _by_key(result)["V5"]
    assert v5.status == "not_computable"  # type: ignore[attr-defined]
    assert "caja neta" in (v5.reason or "")  # type: ignore[attr-defined]


def test_sin_ejercicios_no_revienta() -> None:
    """El contrato del engine prohíbe la excepción: se responde, no se rompe."""
    result = compute_valuation(_series(None), _inputs())
    assert result.metrics == ()
    assert result.fiscal_year is None
    assert "ingerido" in result.notes[0]


def test_partida_ausente_da_no_computable_no_cero() -> None:
    metrics = _by_key(compute_valuation(_series(_mcd_2025(revenue=None)), _inputs()))
    assert metrics["V2"].status == "not_computable"  # type: ignore[attr-defined]
    assert metrics["V2"].value is None  # type: ignore[attr-defined]


# ── Doble staleness ───────────────────────────────────────────────────


def test_cuentas_recientes_no_llevan_aviso() -> None:
    """2025-12-31 → 2026-08-06 son 218 días, por debajo de los 274."""
    result = compute_valuation(_series(_mcd_2025()), _inputs())
    assert result.days_since_fiscal_year_end == 218
    assert result.staleness is None


def test_cuentas_envejecidas_avisan() -> None:
    result = compute_valuation(_series(_mcd_2025()), _inputs(quote_as_of=date(2026, 10, 1)))
    assert result.staleness == "aging"
    assert any("cerró hace" in n for n in result.notes)


def test_cuentas_de_hace_mas_de_ano_y_medio_avisan_mas_fuerte() -> None:
    result = compute_valuation(_series(_mcd_2025()), _inputs(quote_as_of=date(2027, 8, 1)))
    assert result.staleness == "stale"
    assert any("año y medio" in n for n in result.notes)


def test_cotizacion_caduca_se_declara_pero_no_bloquea() -> None:
    result = compute_valuation(_series(_mcd_2025()), _inputs(quote_stale=True))
    assert _by_key(result)["V1"].status == "ok"  # type: ignore[attr-defined]
    assert any("no se ha podido refrescar" in n for n in result.notes)


def test_financiera_avisa_sobre_precio_ventas() -> None:
    result = compute_valuation(_series(_mcd_2025(), is_financial=True), _inputs())
    assert any("financiera" in n for n in result.notes)


# ── Catálogo ──────────────────────────────────────────────────────────


def test_ninguna_metrica_de_valoracion_lleva_banda() -> None:
    """Sin comparables de sector, una banda sería una opinión disfrazada de
    dato: un PER de 25× es caro en una eléctrica y barato en software."""
    for definition in METRIC_CATALOG:
        assert definition.direction is None, f"{definition.key} no debe llevar banda"
        assert definition.to_threshold() is None


def test_estan_catalogadas_pero_fuera_del_seed_de_umbrales() -> None:
    """Las dos mitades de la decisión, que tiran en direcciones opuestas.

    **Catalogadas**: la UI lee su etiqueta y su unidad de una sola fuente. Sin
    eso habría que escribir «PER» a mano en el frontend, que es exactamente cómo
    tres etiquetas acabaron mintiendo sobre su propio número en PHASE-44.9.

    **Fuera del seed**: ninguna lleva `direction`, así que `thresholds_from` las
    descarta y no se siembra ni una fila en `scoring_thresholds`. Un umbral sin
    comparables de sector sería una opinión disfrazada de dato.
    """
    from app.modules.investment.analysis.engine.catalog import (
        ALL_DEFAULT_THRESHOLDS,
        ALL_METRIC_KEYS,
    )

    for definition in METRIC_CATALOG:
        assert definition.key in ALL_METRIC_KEYS, f"{definition.key} debe estar catalogada"
        assert (
            definition.key not in ALL_DEFAULT_THRESHOLDS
        ), f"{definition.key} no debe sembrar umbral"


def test_el_catalogo_agregado_no_tiene_claves_duplicadas() -> None:
    """Una clave repetida haría que dos métricas distintas compartieran
    etiqueta, umbral y celda en la pantalla."""
    from app.modules.investment.analysis.engine.catalog import ALL_METRIC_KEYS

    assert len(ALL_METRIC_KEYS) == len(set(ALL_METRIC_KEYS))
