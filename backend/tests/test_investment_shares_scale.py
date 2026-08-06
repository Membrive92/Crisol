"""Escala del recuento de acciones (PHASE-44.12, bug encontrado el 2026-08-04).

El caso real: McDonald's cambió en su 10-K de 2023 la presentación de las
acciones medias de unidades a millones, y reexpresó los ejercicios anteriores.
El XBRL declara la unidad `shares` en ambos casos, así que nada en el fichero lo
distingue. Como la ingesta se queda con la revisión más reciente de cada año
—que es lo correcto—, toda la serie entró en millones mientras el dinero seguía
en unidades: la caja libre por acción salía 9.515.610 $ en vez de 9,52 $.

Las cifras de estos tests son las REALES de MCD, consultadas en la SEC.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.modules.investment.enums import AccountingStd
from app.modules.investment.fundamentals.canonical import CanonicalStatement, Provenance
from app.modules.investment.fundamentals.normalization import (
    RawFiling,
    detect_scale_exponent,
    normalize,
)
from app.modules.investment.fundamentals.validation import validate_statement

# MCD 2021, tal y como lo reexpresa el 10-K de 2023 (accession 0000063908-24-000072):
# las acciones en MILLONES y el resto en unidades.
_MCD_2021_FACTS = {
    "us-gaap:NetIncomeLoss": Decimal("7545200000"),
    "us-gaap:WeightedAverageNumberOfSharesOutstandingBasic": Decimal("746.3"),
    "us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding": Decimal("751.8"),
    # El testigo: la portada del filing, siempre en unidades reales.
    "dei:EntityCommonStockSharesOutstanding": Decimal("743584718"),
    "us-gaap:Revenues": Decimal("23222900000"),
}


def _raw(facts: dict[str, Decimal]) -> RawFiling:
    return RawFiling(
        fiscal_year=2021,
        fiscal_year_end=date(2021, 12, 31),
        facts=facts,
        filing_accession="0000063908-24-000072",
        currency="USD",
    )


# ── Detección ─────────────────────────────────────────────────────────


def test_detecta_el_factor_exacto_con_datos_reales() -> None:
    """746,3 medias frente a 743.584.718 al cierre: seis órdenes de diferencia
    para dos recuentos de la misma cosa."""
    exponent = detect_scale_exponent(Decimal("746.3"), Decimal("743584718"))
    assert exponent == 6


def test_no_detecta_nada_cuando_la_escala_es_correcta() -> None:
    """Medias y cierre difieren un 0,4% por las recompras: nada que corregir."""
    assert detect_scale_exponent(Decimal("746300000"), Decimal("743584718")) is None


def test_un_desfase_que_no_es_potencia_de_diez_no_se_toca() -> None:
    """Un cociente 2,5x no es un cambio de unidad, es otro problema. Corregirlo
    a ojo convertiría un dato dudoso en uno falso."""
    assert detect_scale_exponent(Decimal("300000000"), Decimal("743584718")) is None


def test_tolera_la_diferencia_por_recompras() -> None:
    """Las dos magnitudes no son idénticas —el cierre refleja las recompras del
    año— así que el cociente ronda 10^6 sin clavarlo. Exigir exactitud sería no
    corregir nunca."""
    # MCD 2025: 713,4 medias vs 710.398.642 al cierre -> ratio 995.793
    assert detect_scale_exponent(Decimal("713.4"), Decimal("710398642")) == 6


# ── Corrección en la ingesta ──────────────────────────────────────────


def test_normalize_corrige_las_acciones_y_deja_traza() -> None:
    statement = normalize(_raw(dict(_MCD_2021_FACTS)))

    assert statement.shares_basic == Decimal("746300000")
    assert statement.shares_diluted == Decimal("751800000")

    corrections = statement.raw_source_ref.get("scale_corrections")
    assert corrections, "la corrección debe quedar registrada, no aplicarse en silencio"
    assert corrections[0]["factor"] == "1000000"
    assert corrections[0]["witness"] == "shares_outstanding_eop"


def test_sin_testigo_no_se_inventa_la_correccion() -> None:
    """Sin testigo no hay prueba, y sin prueba no se toca el dato. La bandera
    del cuadre es la que avisa."""
    facts = dict(_MCD_2021_FACTS)
    del facts["dei:EntityCommonStockSharesOutstanding"]

    statement = normalize(_raw(facts))

    assert statement.shares_basic == Decimal("746.3")  # sin tocar
    assert "scale_corrections" not in statement.raw_source_ref


def test_una_serie_ya_correcta_no_se_altera() -> None:
    """Regresión: la corrección no puede estropear lo que ya estaba bien."""
    facts = dict(_MCD_2021_FACTS)
    facts["us-gaap:WeightedAverageNumberOfSharesOutstandingBasic"] = Decimal("746300000")
    facts["us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding"] = Decimal("751800000")

    statement = normalize(_raw(facts))

    assert statement.shares_basic == Decimal("746300000")
    assert "scale_corrections" not in statement.raw_source_ref


# ── El cuadre que faltaba ─────────────────────────────────────────────


def _statement(**overrides: object) -> CanonicalStatement:
    base: dict[str, object] = {
        "fiscal_year": 2021,
        "fiscal_year_end": date(2021, 12, 31),
        "accounting_std": AccountingStd.GAAP,
        "currency": "USD",
        "filing_accession": "x",
        "item_provenance": {},
        "raw_source_ref": {},
    }
    base.update(overrides)
    return CanonicalStatement(**base)  # type: ignore[arg-type]


def test_el_cuadre_caza_las_dos_escalas_conviviendo() -> None:
    """Es el caso que ningún otro cuadre veía: el balance cuadra, los márgenes
    están en rango, y aun así el dato está mal por un millón."""
    statement = _statement(
        shares_basic=Decimal("746.3"),
        shares_outstanding_eop=Decimal("743584718"),
    )

    flags = validate_statement(statement)
    keys = [f.key for f in flags]

    assert "scale_mismatch:shares_outstanding_eop/shares_basic" in keys
    flag = next(f for f in flags if f.key.startswith("scale_mismatch"))
    assert flag.severity == "red"


def test_el_cuadre_no_salta_con_escalas_coherentes() -> None:
    """Las acciones medias y las del cierre difieren por las recompras del año,
    que en MCD son ~0,4%. Eso no puede disparar la bandera."""
    statement = _statement(
        shares_basic=Decimal("746300000"),
        shares_outstanding_eop=Decimal("743584718"),
    )

    keys = [f.key for f in validate_statement(statement)]

    assert not any(k.startswith("scale_mismatch") for k in keys)


def test_el_cuadre_no_confunde_apalancamiento_con_escala() -> None:
    """Un banco puede tener 20x de activo sobre patrimonio. Eso es negocio, no
    un cambio de unidad, y marcarlo sería un falso positivo que enseña a ignorar
    la bandera."""
    statement = _statement(
        total_assets=Decimal("2000000000000"),
        equity=Decimal("100000000000"),
        item_provenance={"total_liabilities": Provenance.SOURCED},
    )

    keys = [f.key for f in validate_statement(statement)]

    assert not any(k.startswith("scale_mismatch") for k in keys)
