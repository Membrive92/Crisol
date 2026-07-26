"""Tests de las dos reglas puras del catálogo (PHASE-44.8 E1).

`capabilities.py` y `venues.py` no tocan BD, red ni reloj: se prueban sin
fixtures y sin cliente HTTP. Son la fuente ÚNICA de «¿se puede analizar?» y de
«¿qué es una plaza?», así que lo que se fija aquí es lo que ven los tres
consumidores a la vez.
"""

from __future__ import annotations

import pytest

from app.modules.investment.catalog.capabilities import (
    AnalysisCapability,
    AnalysisStatus,
    capabilities_for,
    status_from_evidence,
)
from app.modules.investment.catalog.venues import (
    UNKNOWN,
    is_known_venue,
    normalize_venue,
    venue_label,
    venue_rank,
)

# ── Capacidades ───────────────────────────────────────────────────────


def test_sin_cik_no_hay_analisis_y_se_explica_por_que() -> None:
    """El motor necesita XBRL de la SEC. Un listing no-US no es un error del
    usuario: es una limitación que hay que poder contarle antes del clic."""
    caps = capabilities_for(cik=None)
    assert caps.analysis is AnalysisCapability.UNSUPPORTED
    assert caps.analysis_available is False
    assert caps.reason is not None
    assert "cartera" in caps.reason


@pytest.mark.parametrize("cik", ["", None])
def test_un_cik_vacio_cuenta_como_ausente(cik: str | None) -> None:
    assert capabilities_for(cik=cik).analysis_available is False


def test_con_cik_y_sin_evidencia_se_mantiene_el_comportamiento_previo() -> None:
    """Mover la regla a un solo sitio no cambia su respuesta. Los tres predicados
    que sustituye decían `cik is not None`, así que una fila sin evidencia
    —anterior a la columna, o con el recuento fallido— tiene que responder lo
    mismo; si no, no habría forma de demostrar que el movimiento fue equivalente
    (lección PHASE-34)."""
    caps = capabilities_for(cik="0000063908")
    assert caps.analysis is AnalysisCapability.AVAILABLE
    assert caps.analysis_available is True
    assert caps.reason is None


@pytest.mark.parametrize(
    ("status", "disponible"),
    [
        (AnalysisStatus.OK, True),
        (AnalysisStatus.NO_ANNUAL, False),
        (AnalysisStatus.NON_GAAP, False),
        (AnalysisStatus.NOT_SUPPORTED, False),
    ],
)
def test_la_evidencia_manda_cuando_existe(status: AnalysisStatus, disponible: bool) -> None:
    """El seam de la Entrega 2 ya está probado: en cuanto la columna exista, SPY
    (`no_annual`) y SAN (`non_gaap`) dejan de prometerse como analizables sin
    tocar a ningún consumidor."""
    caps = capabilities_for(cik="0000884394", analysis_status=status.value)
    assert caps.analysis_available is disponible
    if not disponible:
        assert caps.reason


def test_un_estado_desconocido_no_revienta_y_no_promete_nada() -> None:
    """La columna es `String` para poder crecer sin migración. Un valor que este
    código todavía no conoce se trata como "no comprobado", no como excepción."""
    caps = capabilities_for(cik="0000884394", analysis_status="algo_que_vendra_luego")
    assert caps.analysis is AnalysisCapability.UNKNOWN
    assert caps.analysis_available is False


# ── Evidencia: de lo que cuenta el adapter al valor que se persiste ───


def test_los_tres_ceros_no_son_el_mismo_cero() -> None:
    """Recuentos verificados ejecutando la librería contra la SEC de verdad. Lo
    que separa a SPY de Santander no es que uno tenga menos datos: es que SPY no
    es una empresa y Santander sí, sólo que publica en IFRS. Decirle al usuario
    que Santander "no publica cuentas" sería sencillamente falso."""
    mcd = status_from_evidence(
        cik="0000063908", annual_report_count=33, foreign_annual_report_count=0
    )
    spy = status_from_evidence(
        cik="0000884394", annual_report_count=0, foreign_annual_report_count=0
    )
    san = status_from_evidence(
        cik="0000891478", annual_report_count=0, foreign_annual_report_count=25
    )

    assert mcd == AnalysisStatus.OK.value
    assert spy == AnalysisStatus.NO_ANNUAL.value
    assert san == AnalysisStatus.NON_GAAP.value

    # Y cada uno se traduce a un motivo distinto y cierto.
    assert capabilities_for(cik="0000063908", analysis_status=mcd).analysis_available is True
    assert "fondo" in (capabilities_for(cik="0000884394", analysis_status=spy).reason or "")
    assert "IFRS" in (capabilities_for(cik="0000891478", analysis_status=san).reason or "")


def test_sin_recuento_no_se_persiste_veredicto() -> None:
    """`None` es «no lo comprobé», no «no tiene». Un fallo de red al contar no
    puede marcar un valor como no analizable para siempre."""
    assert status_from_evidence(cik="0000063908", annual_report_count=None) is None


def test_sin_cik_la_evidencia_sobra() -> None:
    """Un listing no-US no necesita que nadie cuente nada: no hay EDGAR."""
    assert (
        status_from_evidence(cik=None, annual_report_count=None)
        == AnalysisStatus.NOT_SUPPORTED.value
    )


# ── Plazas ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("pais", ["US", "us", " US ", "USA", "GLOBAL", ""])
def test_un_pais_no_es_una_plaza(pais: str) -> None:
    """El bug de origen de PHASE-44.8: el frontend escribía `'US'` en
    `securities.exchange`, y como la restricción única es `(ticker, exchange)`,
    `MCD/US` y `MCD/NYSE` eran dos filas del mismo valor. `UNKNOWN` dice "no lo
    sé"; `'US'` afirmaba una plaza que no existe."""
    assert normalize_venue(pais) == UNKNOWN


def test_none_es_desconocido() -> None:
    assert normalize_venue(None) == UNKNOWN


@pytest.mark.parametrize(
    ("crudo", "esperado"),
    [
        ("NYSE", "NYSE"),
        ("nyse", "NYSE"),
        ("Nasdaq", "NASDAQ"),  # la etiqueta que escribe la SEC
        ("OTC", "OTC"),
        ("CBOE", "CBOE"),
        ("NYSE American", "NYSE"),
        ("OTCQB", "OTC"),
        ("BATS", "CBOE"),
    ],
)
def test_las_plazas_de_la_sec_se_normalizan_a_mayusculas(crudo: str, esperado: str) -> None:
    """Mayúsculas porque es lo que ya persiste el resto del módulo: los tests de
    endpoints mandan `NYSE` y el validador del schema sube `nyse`."""
    assert normalize_venue(crudo) == esperado


@pytest.mark.parametrize("mic", ["XMAD", "XAMS", "XETR", "BVMF"])
def test_un_mic_iso_se_respeta_tal_cual(mic: str) -> None:
    """Los cuatro caracteres de un MIC ISO 10383 pasan sin traducir: es lo que
    devolverá el proveedor externo de la Entrega 5, y traducirlo a una etiqueta
    propia perdería el dato bueno."""
    assert normalize_venue(mic) == mic


@pytest.mark.parametrize("basura", ["mercado continuo", "bolsa de madrid", "???????"])
def test_lo_que_no_se_reconoce_es_desconocido_no_inventado(basura: str) -> None:
    assert normalize_venue(basura) == UNKNOWN


def test_la_prominencia_ordena_la_cotizacion_principal_antes_del_otc() -> None:
    """Un mismo emisor sale varias veces (el ADR no patrocinado en OTC además de
    su cotización principal). El orden no es estético: decide qué fila se queda
    cuando la Entrega 2 colapse por CIK."""
    assert venue_rank("NYSE") < venue_rank("OTC")
    assert venue_rank("NASDAQ") < venue_rank("OTC")
    assert venue_rank("XMAD") > venue_rank("OTC")  # lo no catalogado, al final


def test_la_etiqueta_humana_no_inventa_traducciones() -> None:
    assert venue_label("NASDAQ") == "Nasdaq"
    assert venue_label("XMAD") == "XMAD"


def test_un_mic_externo_no_cuenta_como_plaza_de_la_sec() -> None:
    """Lo usa la guarda que vigila que nadie vuelva a colar un país —o un MIC
    europeo— donde se espera una plaza estadounidense."""
    assert is_known_venue("NYSE") is True
    assert is_known_venue("XMAD") is False
    assert is_known_venue("US") is False
