"""Parser FULINS y su contrato con el mapa de sufijos (PHASE-44.14, ADR-0010).

El fixture (`tests/fixtures/firds_fulins_e_sample.xml`) está construido con
registros REALES de los ficheros del 2026-08-01 —ESMA y FCA—, sobre incluido:
Inditex, Santander y Allianz tal y como los publica el regulador, más los
contraejemplos que ejercen cada rama del filtro (un MTF, un CFI no-ES, un
listing terminado). La forma de salida se prueba, no se deduce ([PHASE-44.6]).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from app.modules.investment.catalog.firds import (
    SEED_SEGMENT_TO_OPERATING,
    FirdsRecord,
    collapse_records,
    parse_fulins,
)
from app.modules.investment.pricing.adapters.yfinance import suffix_for_venue

FIXTURE = Path(__file__).parent / "fixtures" / "firds_fulins_e_sample.xml"
TODAY = date(2026, 8, 7)


def _parse() -> list[FirdsRecord]:
    with FIXTURE.open("rb") as fh:
        return list(parse_fulins(fh, today=TODAY))


class TestParser:
    def test_extrae_los_campos_del_registro_real(self) -> None:
        inditex = next(r for r in _parse() if r.isin == "ES0148396007")
        assert inditex.mic == "XMAD"
        assert inditex.currency == "EUR"
        assert inditex.cfi.startswith("ES")
        assert "INDITEX" in inditex.name.upper()
        # El ShrtNm de FIRDS lleva el ticker local: es lo que hace que buscar
        # `ITX` encuentre a Inditex por DATOS, sin lista de alias.
        assert inditex.short_name is not None
        assert inditex.short_name.startswith("ITX/")

    def test_la_fca_publica_londres_en_libras_no_en_peniques(self) -> None:
        """Verificado contra el fichero real: `NtnlCcy=GBP`. Los peniques (GBp)
        son cosa del proveedor de precios, y su normalización vive allí."""
        shell = next(r for r in _parse() if r.isin == "GB00BP6MXD84")
        assert shell.mic == "XLON"
        assert shell.currency == "GBP"

    def test_un_mtf_no_pasa_el_filtro(self) -> None:
        """El fixture lleva un registro real de EBLX (MTF): cotiza lo mismo que
        la plaza principal y duplicaría cada emisor N veces."""
        assert all(r.segment_mic != "EBLX" for r in _parse())

    def test_un_cfi_no_es_no_pasa_el_filtro(self) -> None:
        """Registro real con CFI `EDSNDR` (depositary receipt) en plaza
        principal: la plaza es buena, el tipo de instrumento no."""
        assert all(r.cfi.startswith("ES") for r in _parse())

    def test_un_listing_terminado_no_pasa_el_filtro(self) -> None:
        """El fixture lleva un registro real con `TermntnDt` pasada."""
        records = _parse()
        assert all(r.termination_date is None or r.termination_date > TODAY for r in records)

    def test_el_segmento_se_normaliza_al_mic_operativo(self) -> None:
        """El hallazgo que obligó a desviarse del plan: FIRDS reporta el mercado
        principal alemán como `XETA`, nunca `XETR`. Sin la normalización,
        Alemania entera quedaba fuera — Allianz no aparecía en ninguna plaza."""
        allianz = [r for r in _parse() if r.isin == "DE0008404005"]
        assert allianz, "Allianz no pasó el filtro"
        assert {r.mic for r in allianz} == {"XETR"}
        assert {r.segment_mic for r in allianz} == {"XETA", "XETU", "XEMA"}


class TestColapso:
    def test_tres_segmentos_de_xetra_son_una_fila(self) -> None:
        collapsed = collapse_records(iter(_parse()))
        allianz = collapsed.get(("DE0008404005", "XETR"))
        assert allianz is not None
        # Y gana el parqué principal, no el off-book ni el midpoint.
        assert allianz.segment_mic == "XETA"

    def test_el_colapso_no_depende_del_orden(self) -> None:
        records = _parse()
        forward = collapse_records(iter(records))
        backward = collapse_records(iter(reversed(records)))
        assert forward == backward


class TestContratoConElProveedorDePrecios:
    def test_todo_mic_sembrado_tiene_sufijo_en_el_mapa_de_precios(self) -> None:
        """El seguro de que un valor adoptado desde el directorio SIEMPRE se
        puede cotizar: cada MIC operativo que el seed puede almacenar tiene su
        sufijo en `pricing/adapters/yfinance.py`. Si alguien añade un mercado al
        seed sin darle sufijo, esto lo para en CI — no un usuario en producción
        con una posición que no valora."""
        for operating in set(SEED_SEGMENT_TO_OPERATING.values()):
            assert suffix_for_venue(operating) is not None, (
                f"{operating} se puede sembrar pero el proveedor de precios "
                "no sabe componer su símbolo"
            )
