"""Tests de la capa de ingesta pura (PHASE-44.6): mapeo XBRL → canónico.

Sin red y sin BD: los hechos son sintéticos, pero cada caso reproduce algo que
apareció DE VERDAD en el cruzado contra MCD, Realty Income y JNJ. Cuando un test
dice "como MCD", es que MCD lo hace así en su 10-K.
"""

from __future__ import annotations

import ast
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.modules.investment.fundamentals.adapters.concept_map import (
    COMBINED_MAP,
    CONCEPT_MAP,
    CONDITIONAL_ZERO_ITEMS,
    DEI,
    DEI_MAP,
    IMPUTABLE_ZERO_ITEMS,
    NET_LINE_FALLBACKS,
    US_GAAP,
    qualify,
)
from app.modules.investment.fundamentals.canonical import (
    CANONICAL_ITEM_SET,
    CanonicalStatement,
    Provenance,
)
from app.modules.investment.fundamentals.normalization import (
    RawFiling,
    mapped_items,
    normalize,
)
from app.modules.investment.fundamentals.validation import validate_statement


def dec(value: object) -> Decimal:
    return Decimal(str(value))


def _raw(fiscal_year: int = 2024, **tags: object) -> RawFiling:
    """Un filing sintético. Las claves son etiquetas `us-gaap`; con el prefijo
    `dei__` van al namespace de portada."""
    facts: dict[str, Decimal] = {}
    for tag, value in tags.items():
        namespace, name = (DEI, tag[5:]) if tag.startswith("dei__") else (US_GAAP, tag)
        facts[qualify(namespace, name)] = dec(value)
    return RawFiling(
        fiscal_year=fiscal_year,
        fiscal_year_end=date(fiscal_year, 12, 31),
        facts=facts,
        filing_accession="0000063908-25-000012",
    )


def _flag_keys(statement: CanonicalStatement) -> set[str]:
    return {flag["key"] for flag in statement.raw_source_ref["quality_flags"]}


# ── 1. Mapeo por candidatos ───────────────────────────────────────────


def test_gana_el_primer_candidato_con_dato() -> None:
    """La caja estricta gana a la que incluye efectivo restringido: el
    restringido no es caja disponible y leerlo primero inflaría la liquidez."""
    statement = normalize(
        _raw(
            CashAndCashEquivalentsAtCarryingValue=1_000,
            CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents=1_800,
        )
    )
    assert statement.cash == dec(1_000)
    assert mapped_items(statement)["cash"] == ["us-gaap:CashAndCashEquivalentsAtCarryingValue"]


def test_cae_al_siguiente_candidato_si_el_primero_no_esta() -> None:
    """MCD etiqueta sus clientes como `AccountsNotesAndLoansReceivableNetCurrent`."""
    statement = normalize(_raw(AccountsNotesAndLoansReceivableNetCurrent=2_500))
    assert statement.receivables == dec(2_500)


def test_la_etiqueta_de_signo_invertido_entra_en_negativo() -> None:
    """Realty Income publica sus 'distribuciones en exceso del resultado' en
    positivo, pero es un saldo DEUDOR: son reservas negativas."""
    statement = normalize(_raw(AccumulatedDistributionsInExcessOfNetIncome=10_528))
    assert statement.retained_earnings == dec(-10_528)


def test_las_partidas_del_canonico_sin_dato_quedan_huecas() -> None:
    """Un hueco es `None`, jamás 0 (§4.5): `revenue` no está en la lista blanca."""
    assert normalize(_raw(Assets=100)).revenue is None


# ── 2. Combinación de etiquetas ───────────────────────────────────────


def test_combina_emisiones_menos_amortizaciones_de_deuda() -> None:
    """Ninguna de las tres empresas publica la variación neta de deuda con una
    sola etiqueta."""
    statement = normalize(
        _raw(ProceedsFromIssuanceOfLongTermDebt=5_000, RepaymentsOfLongTermDebt=1_400)
    )
    assert statement.debt_change == dec(3_600)
    assert statement.provenance_of("debt_change") is Provenance.SOURCED


def test_la_combinacion_no_exige_el_grupo_completo() -> None:
    """Una empresa que solo amortizó no publica emisiones, y su variación neta es
    exactamente esa amortización en negativo — no un hueco."""
    assert normalize(_raw(RepaymentsOfLongTermDebt=2_000)).debt_change == dec(-2_000)


def test_el_pretax_partido_por_jurisdiccion_se_suma() -> None:
    """MCD nunca publica el resultado antes de impuestos consolidado, solo el
    desglose Domestic/Foreign. Sumarlos da el total REPORTADO, así que sigue
    siendo dato de la empresa: `sourced`."""
    statement = normalize(
        _raw(
            IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic=3_291,
            IncomeLossFromContinuingOperationsBeforeIncomeTaxesForeign=7_606,
        )
    )
    assert statement.pretax_income == dec(10_897)
    assert statement.provenance_of("pretax_income") is Provenance.SOURCED


def test_el_mapeo_directo_gana_a_la_combinacion() -> None:
    """Si el emisor publica el consolidado, no se reconstruye por jurisdicciones."""
    statement = normalize(
        _raw(
            IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest=1_155,
            IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic=900,
            IncomeLossFromContinuingOperationsBeforeIncomeTaxesForeign=200,
        )
    )
    assert statement.pretax_income == dec(1_155)


def test_el_arrendamiento_sin_partir_degrada_a_derived() -> None:
    """Con el balance no clasificado (el REIT) la deuda por arrendamiento viene
    sin partir. Acumularla toda en el tramo no corriente es un SUPUESTO sobre la
    parte corriente, no una identidad: por eso no puede salir `sourced`."""
    statement = normalize(_raw(OperatingLeaseLiability=1_200, FinanceLeaseLiability=300))
    assert statement.lease_liabilities_noncurrent == dec(1_500)
    assert statement.provenance_of("lease_liabilities_noncurrent") is Provenance.DERIVED


# ── 3. Namespace `dei` ────────────────────────────────────────────────


def test_las_acciones_en_circulacion_salen_de_la_portada() -> None:
    """Ni MCD ni JNJ publican `CommonStockSharesOutstanding` en us-gaap: las
    acciones en circulación solo están en la cubierta del 10-K."""
    statement = normalize(_raw(dei__EntityCommonStockSharesOutstanding=712_000_000))
    assert statement.shares_outstanding_eop == dec(712_000_000)
    assert mapped_items(statement)["shares_outstanding_eop"] == [
        "dei:EntityCommonStockSharesOutstanding"
    ]


def test_us_gaap_gana_a_la_portada() -> None:
    """La portada es el último recurso: su fecha es la de cubierta, posterior al
    cierre fiscal, así que el dato del ejercicio siempre es mejor."""
    statement = normalize(
        _raw(CommonStockSharesOutstanding=700, dei__EntityCommonStockSharesOutstanding=712)
    )
    assert statement.shares_outstanding_eop == dec(700)


# ── 4. Líneas netas ───────────────────────────────────────────────────


def test_las_etiquetas_partidas_ganan_a_la_linea_neta() -> None:
    """JNJ publica las dos cosas: el deterioro suelto y un neto que lo mezcla con
    plusvalías. Con el desglose disponible, la neta sobra."""
    statement = normalize(
        _raw(
            AssetImpairmentCharges=204,
            GainLossOnSalesOfAssetsAndAssetImpairmentCharges=263,
        )
    )
    assert statement.impairments == dec(204)
    assert statement.provenance_of("impairments") is Provenance.SOURCED


def test_la_linea_neta_alimenta_deterioros_y_anula_las_plusvalias() -> None:
    """Sin desglose, el neto va a deterioros y las plusvalías quedan a cero: como
    `ebit_clean = ebit + deterioros − plusvalías`, alimentar las dos partidas con
    la misma línea doblaría el ajuste."""
    statement = normalize(_raw(GainLossOnSalesOfAssetsAndAssetImpairmentCharges=263))
    assert statement.impairments == dec(263)
    assert statement.provenance_of("impairments") is Provenance.DERIVED
    assert statement.gains_on_sale_of_business == dec(0)
    assert statement.provenance_of("gains_on_sale_of_business") is Provenance.IMPUTED_ZERO
    assert statement.raw_source_ref["notes"], "la absorción del neto debe dejar aviso"


# ── 5. Ausencia vs cero ───────────────────────────────────────────────


def test_una_ausencia_de_la_lista_blanca_es_cero_imputado() -> None:
    """En XBRL nadie etiqueta lo que vale cero: sin deuda a corto, el concepto no
    aparece. Tratarlo como hueco dejaría `total_debt` sin calcular en empresas
    perfectamente sanas."""
    statement = normalize(_raw(Assets=1_000))
    assert statement.short_term_debt == dec(0)
    assert statement.provenance_of("short_term_debt") is Provenance.IMPUTED_ZERO


def test_una_ausencia_fuera_de_la_lista_sigue_siendo_hueco() -> None:
    """Un servicio no tiene coste de ventas y un balance no clasificado no tiene
    activo corriente. La respuesta honesta es 'no computable', no un cero que
    convertiría un margen imposible en un número creíble."""
    statement = normalize(_raw(Assets=1_000))
    assert statement.cogs is None
    assert statement.current_assets is None


def test_los_intereses_solo_son_cero_si_no_hay_deuda_viva() -> None:
    """Con la deuda a largo publicada a cero, el gasto financiero ausente es cero
    de verdad."""
    statement = normalize(_raw(Assets=1_000, LongTermDebtNoncurrent=0))
    assert statement.interest_expense == dec(0)
    assert statement.provenance_of("interest_expense") is Provenance.IMPUTED_ZERO


def test_con_deuda_viva_unos_intereses_ausentes_son_hueco() -> None:
    """Imputar cero aquí regalaría una cobertura de intereses infinita justo en la
    empresa apalancada donde esa métrica es la que importa."""
    statement = normalize(_raw(Assets=1_000, LongTermDebtNoncurrent=5_000))
    assert statement.interest_expense is None


def test_con_la_deuda_a_largo_desconocida_los_intereses_siguen_huecos() -> None:
    """`long_term_debt` NO está en la lista blanca a propósito, así que su
    ausencia significa 'no lo sé', no 'no hay'. Y sin saber si hay deuda no se
    puede afirmar que los intereses sean cero: dar por buena la cadena de
    ausencias es justo como se fabrica una empresa sin deuda que sí la tiene."""
    statement = normalize(_raw(Assets=1_000, NetIncomeLoss=100, IncomeTaxExpenseBenefit=30))
    assert statement.interest_expense is None
    assert statement.long_term_debt is None


# ── 6. Derivaciones de ingesta ────────────────────────────────────────


def test_el_ebit_ausente_se_deriva_del_pretax_mas_intereses() -> None:
    """JNJ dejó de publicar `OperatingIncomeLoss` en 2015 y los REIT no tienen
    línea operativa: el EBIT hay que derivarlo."""
    statement = normalize(
        _raw(
            IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest=1_155,
            InterestExpenseOperating=1_134,
        )
    )
    assert statement.ebit == dec(2_289)
    assert statement.provenance_of("ebit") is Provenance.DERIVED


def test_el_ebit_derivado_cae_a_neto_mas_impuestos_sin_pretax() -> None:
    """Segundo plato: reconstruir el pretax ignora minoritarios y actividades
    discontinuadas, pero es mejor que un hueco."""
    statement = normalize(_raw(NetIncomeLoss=280, IncomeTaxExpenseBenefit=70, InterestExpense=50))
    assert statement.ebit == dec(400)


def test_el_ebit_publicado_no_se_deriva() -> None:
    statement = normalize(_raw(OperatingIncomeLoss=12_393, InterestExpense=500))
    assert statement.ebit == dec(12_393)
    assert statement.provenance_of("ebit") is Provenance.SOURCED


def test_el_pasivo_total_ausente_sale_de_activo_menos_patrimonio() -> None:
    """MCD no publica `Liabilities` y su patrimonio es NEGATIVO por recompras: la
    resta sigue valiendo."""
    statement = normalize(_raw(Assets=56_147, StockholdersEquity=-3_797))
    assert statement.total_liabilities == dec(59_944)
    assert statement.provenance_of("total_liabilities") is Provenance.DERIVED


# ── 7. Cuadres ────────────────────────────────────────────────────────


def test_el_cuadre_del_balance_no_es_verificable_con_el_pasivo_derivado() -> None:
    """Derivado como activo − patrimonio, el cuadre se cumple por construcción.
    Presentarlo como superado engañaría más que no comprobarlo."""
    statement = normalize(_raw(Assets=56_147, StockholdersEquity=-3_797))
    assert "balance_identity_unverifiable" in _flag_keys(statement)
    assert "balance_identity_broken" not in _flag_keys(statement)


def test_un_balance_descuadrado_levanta_bandera() -> None:
    statement = normalize(_raw(Assets=1_000, Liabilities=300, StockholdersEquity=200))
    assert "balance_identity_broken" in _flag_keys(statement)


def test_un_balance_que_cuadra_no_levanta_banderas() -> None:
    statement = normalize(
        _raw(Assets=1_000, Liabilities=600, StockholdersEquity=400, Revenues=500, NetIncomeLoss=50)
    )
    assert _flag_keys(statement) == set()


def test_un_margen_neto_imposible_levanta_bandera() -> None:
    """Fuera de [−1, 1] no suele haber una empresa rara: hay una escala mal
    aplicada o una cifra de negocio mapeada a una partida parcial."""
    statement = normalize(_raw(Revenues=100, NetIncomeLoss=900))
    assert "net_margin_out_of_range" in _flag_keys(statement)


def test_componentes_que_se_pasan_de_su_total_levantan_bandera() -> None:
    """Sumar más que el total solo puede ser una etiqueta contada dos veces."""
    statement = normalize(
        _raw(
            AssetsCurrent=100,
            CashAndCashEquivalentsAtCarryingValue=80,
            AccountsReceivableNetCurrent=50,
        )
    )
    assert "components_exceed_total" in _flag_keys(statement)


def test_los_cuadres_nunca_abortan_la_ingesta() -> None:
    """Un cuadre roto marca el ejercicio como sospechoso, no lo descarta: el
    usuario prefiere verlo con una advertencia a no verlo."""
    statement = normalize(_raw(Assets=1_000, Liabilities=300, StockholdersEquity=200))
    assert statement.total_assets == dec(1_000)


def test_los_componentes_por_debajo_del_total_son_normales() -> None:
    """Casi todo balance tiene partidas 'otros' que el canónico no modela: la
    comprobación es de un solo lado a propósito."""
    statement = CanonicalStatement(
        fiscal_year=2024,
        fiscal_year_end=date(2024, 12, 31),
        accounting_std=normalize(_raw()).accounting_std,
        current_assets=dec(1_000),
        cash=dec(100),
    )
    assert validate_statement(statement) == ()


# ── 8. Traza de auditoría ─────────────────────────────────────────────


def test_la_traza_dice_de_donde_sale_cada_partida() -> None:
    """`raw_source_ref` responde '¿de dónde salió este número?' sin adivinanzas
    [Dec.13]."""
    statement = normalize(_raw(Assets=1_000, StockholdersEquity=400))
    mapping = statement.raw_source_ref["mapping"]
    assert mapping["total_assets"]["concepts"] == ["us-gaap:Assets"]
    assert mapping["total_liabilities"]["provenance"] == "derived"
    assert mapping["total_liabilities"]["rule"] == "total_assets - equity"
    assert mapping["short_term_debt"]["provenance"] == "imputed_zero"


# ── 9. Coherencia del propio mapeo ────────────────────────────────────


def test_el_mapeo_solo_referencia_partidas_canonicas() -> None:
    """Un typo en una clave sería una partida que nunca se rellena y nadie echa
    de menos."""
    claves = (
        set(CONCEPT_MAP)
        | set(COMBINED_MAP)
        | set(DEI_MAP)
        | set(IMPUTABLE_ZERO_ITEMS)
        | set(CONDITIONAL_ZERO_ITEMS)
        | {spec.into for spec in NET_LINE_FALLBACKS}
        | {spec.zeroed for spec in NET_LINE_FALLBACKS}
    )
    assert claves <= CANONICAL_ITEM_SET


def test_ninguna_etiqueta_alimenta_dos_partidas() -> None:
    """La misma etiqueta en dos partidas contaría el mismo dinero dos veces."""
    vistas: dict[str, str] = {}
    for item, candidatos in CONCEPT_MAP.items():
        for tag in candidatos:
            assert tag not in vistas, f"'{tag}' alimenta '{vistas[tag]}' y '{item}'"
            vistas[tag] = item


def test_una_partida_no_puede_ser_cero_incondicional_y_condicional() -> None:
    """La lista incondicional ganaría y la condición no se evaluaría nunca."""
    assert not (set(IMPUTABLE_ZERO_ITEMS) & set(CONDITIONAL_ZERO_ITEMS))


def test_el_calendario_de_vencimientos_no_es_un_flujo_de_caja() -> None:
    """`LongTermDebtMaturitiesRepaymentsOfPrincipal*` es la tabla de vencimientos
    de la memoria, no una amortización del ejercicio. Un emparejado por subcadena
    'RepaymentsOf' se la tragaría y contaría deuda futura como flujo."""
    etiquetas = {tag for candidatos in CONCEPT_MAP.values() for tag in candidatos}
    etiquetas |= {tag for spec in COMBINED_MAP.values() for tag in spec.add + spec.sub}
    assert not [tag for tag in etiquetas if tag.startswith("LongTermDebtMaturities")]


def test_la_ingesta_no_importa_io() -> None:
    """El mapeo y la normalización son puros igual que el engine: así se pueden
    cruzar contra fixtures sin levantar BD ni pegarle a la SEC."""
    prohibidos = {"sqlalchemy", "httpx", "requests", "asyncpg", "app.core.database"}
    base = Path(__file__).resolve().parents[1] / "app/modules/investment/fundamentals"
    modulos = [
        base / "canonical.py",
        base / "normalization.py",
        base / "validation.py",
        base / "adapters/concept_map.py",
    ]
    for modulo in modulos:
        arbol = ast.parse(modulo.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                nombres = [alias.name for alias in nodo.names]
            elif isinstance(nodo, ast.ImportFrom):
                nombres = [nodo.module or ""]
            else:
                continue
            for nombre in nombres:
                raiz = nombre.split(".")[0]
                assert (
                    raiz not in prohibidos and nombre not in prohibidos
                ), f"{modulo.name} importa '{nombre}': la ingesta debe ser pura"


# ── 10. Caso completo ─────────────────────────────────────────────────


def test_un_filing_completo_al_estilo_mcd() -> None:
    """Recorrido entero con los rasgos reales de MCD: patrimonio negativo, sin
    `Liabilities`, sin pretax consolidado, sin acciones en us-gaap y sin COGS."""
    statement = normalize(
        _raw(
            Assets=56_147,
            StockholdersEquity=-3_797,
            CashAndCashEquivalentsAtCarryingValue=1_090,
            AccountsNotesAndLoansReceivableNetCurrent=2_724,
            OperatingIncomeLoss=12_393,
            Revenues=25_920,
            NetIncomeLoss=8_223,
            IncomeTaxExpenseBenefit=2_190,
            InterestExpense=1_360,
            IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic=3_291,
            IncomeLossFromContinuingOperationsBeforeIncomeTaxesForeign=7_606,
            ProceedsFromIssuanceOfLongTermDebt=3_500,
            RepaymentsOfLongTermDebt=3_572,
            dei__EntityCommonStockSharesOutstanding=712_000_000,
        )
    )

    assert statement.equity == dec(-3_797)
    assert statement.total_liabilities == dec(59_944)  # derivada
    assert statement.pretax_income == dec(10_897)  # combinada
    assert statement.ebit == dec(12_393)  # publicada, no derivada
    assert statement.debt_change == dec(-72)  # combinada, negativa
    assert statement.shares_outstanding_eop == dec(712_000_000)  # dei
    assert statement.cogs is None  # un servicio no tiene coste de ventas
    assert _flag_keys(statement) == {"balance_identity_unverifiable"}


@pytest.mark.parametrize("item", sorted(IMPUTABLE_ZERO_ITEMS))
def test_toda_la_lista_blanca_se_imputa_a_cero(item: str) -> None:
    """Ninguna partida de la lista puede quedar hueca en un filing vacío: si una
    se queda fuera del recorrido, la lista miente."""
    statement = normalize(_raw())
    assert statement.get(item) == dec(0)
    assert statement.provenance_of(item) is Provenance.IMPUTED_ZERO
