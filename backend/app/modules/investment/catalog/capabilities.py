"""Qué se puede hacer con un valor del catálogo — fuente ÚNICA de la regla
(PHASE-44.8 E1, ADR-0008).

Antes de esta capa la pregunta «¿se puede analizar este valor?» estaba escrita
tres veces —`schemas.SecurityResponse.analysis_available`, la construcción del hit
en `router.search_endpoint` y la guarda de `fundamentals.service._download`— y las
tres decían `cik is not None`.

Ese predicado **es falso**: SPY (CIK 0000884394) y QQQ (0001067839) tienen CIK y
no presentan 10-K, así que salían marcados como analizables. Al elegirlos, la
ingesta fallaba y el análisis contestaba «lanza la ingesta primero»: un callejón
donde el mensaje manda a hacer justo lo que acaba de fallar.

La respuesta correcta no se puede calcular al vuelo —distinguir «tiene CIK pero
no presenta anuales» de «presenta 20-F con IFRS» exige contar filings, o sea
red, y el buscador tiene que responder sin salir de la máquina—, así que la
evidencia se cuenta UNA vez al resolver el valor y se persiste en
`securities.analysis_status`. Aquí sólo se traduce.

Sin evidencia (`analysis_status IS NULL`) la respuesta es la misma que daban los
tres predicados que esta función sustituye. Eso no es una concesión: es lo que
permite demostrar que mover la regla no cambió ningún resultado (lección
PHASE-34), y lo que hace que un fallo de red al contar no marque un valor como
no analizable para siempre.

Módulo PURO: sin BD, sin red, sin reloj.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from app.modules.investment.enums import AccountingStd


class AnalysisCapability(enum.StrEnum):
    """Si el motor fundamental puede correr sobre este valor."""

    AVAILABLE = "available"
    """Hay CIK y, si se comprobó, evidencia de 10-K utilizables."""

    UNKNOWN = "unknown"
    """La columna trae un estado que este código todavía no conoce. No se promete
    nada, pero tampoco se trata como error: la columna es `String` para poder
    crecer sin migración."""

    UNSUPPORTED = "unsupported"
    """Sin CIK: no hay filing en EDGAR, así que no hay nada que ingerir."""


class AnalysisStatus(enum.StrEnum):
    """Evidencia persistida en `securities.analysis_status`.

    La escribe `status_from_evidence` al resolver el valor y se refresca en cada
    reintento: es una foto, no una verdad eterna. Quien hoy no presenta 10-K
    puede presentarlo el año que viene.
    """

    OK = "ok"
    """Presenta 10-K con taxonomía us-gaap. Ej.: MCD."""

    NO_ANNUAL = "no_annual"
    """Tiene CIK y no presenta anuales. Ej.: SPY, QQQ (son trusts)."""

    NON_GAAP = "non_gaap"
    """Publica cuentas anuales, pero como 20-F con taxonomía IFRS, contra un
    `concept_map` us-gaap. Ej.: SAN (25 veintiefes), ASML (27), SAP."""

    NOT_SUPPORTED = "not_supported"
    """Sin CIK (listing no-US adoptado sólo para cartera)."""


@dataclass(frozen=True)
class CapabilitySet:
    """Veredicto por valor. `reason` es texto para el usuario, no para logs."""

    analysis: AnalysisCapability
    reason: str | None = None

    @property
    def analysis_available(self) -> bool:
        """El contrato público del schema. `UNKNOWN` cuenta como **no**
        disponible: prometer un análisis que luego falla es peor que negarlo y
        resolverlo al añadir el valor."""
        return self.analysis is AnalysisCapability.AVAILABLE


_NO_CIK = (
    "No es un emisor con filings en EDGAR (sin CIK), así que no hay estados "
    "financieros que ingerir. Se puede llevar en la cartera, pero no analizar."
)

_NO_ANNUAL = (
    "Tiene ficha en la SEC pero no presenta cuentas anuales (10-K): suele ser un "
    "fondo o un vehículo, no una empresa operativa."
)

_NON_GAAP = (
    "Presenta sus cuentas con taxonomía IFRS (formulario 20-F), y el mapa de "
    "partidas de este módulo está construido sobre US-GAAP."
)

_UNVERIFIED = "Aún no se ha comprobado que presente cuentas anuales utilizables."

_STATUS_MAP: dict[AnalysisStatus, CapabilitySet] = {
    AnalysisStatus.OK: CapabilitySet(analysis=AnalysisCapability.AVAILABLE),
    AnalysisStatus.NO_ANNUAL: CapabilitySet(
        analysis=AnalysisCapability.UNSUPPORTED, reason=_NO_ANNUAL
    ),
    AnalysisStatus.NON_GAAP: CapabilitySet(
        analysis=AnalysisCapability.UNSUPPORTED, reason=_NON_GAAP
    ),
    AnalysisStatus.NOT_SUPPORTED: CapabilitySet(
        analysis=AnalysisCapability.UNSUPPORTED, reason=_NO_CIK
    ),
}


def capabilities_for(*, cik: str | None, analysis_status: str | None = None) -> CapabilitySet:
    """Veredicto a partir de lo que se sabe de la fila.

    Sin CIK no hay análisis posible, y eso no depende de ninguna evidencia. Con
    CIK manda `analysis_status`; si está a NULL —una fila anterior a la columna, o
    un valor cuyo recuento falló— se responde `AVAILABLE`, que es exactamente lo
    que contestaban los tres sitios que esta función sustituye.

    Args:
        cik: Central Index Key de la SEC, o `None` para un valor no-US.
        analysis_status: valor de `securities.analysis_status` si ya se comprobó.
            Un valor desconocido se trata como no comprobado, no como error: la
            columna es `String` precisamente para poder crecer sin migración.

    Returns:
        El veredicto, con motivo cuando el análisis no está disponible.
    """
    if not cik:
        return CapabilitySet(analysis=AnalysisCapability.UNSUPPORTED, reason=_NO_CIK)
    if analysis_status is None:
        return CapabilitySet(analysis=AnalysisCapability.AVAILABLE)
    try:
        status = AnalysisStatus(analysis_status)
    except ValueError:
        return CapabilitySet(analysis=AnalysisCapability.UNKNOWN, reason=_UNVERIFIED)
    return _STATUS_MAP[status]


def accounting_std_from_status(analysis_status: str | None) -> AccountingStd:
    """Norma contable que la EVIDENCIA respalda, no la que se supone.

    `non_gaap` significa exactamente una cosa comprobada: este emisor no
    presenta 10-K y sí presenta 20-F con taxonomía `ifrs-full` (SAN: 0 y 25).
    Etiquetarlo `IFRS` no es cosmético — `thresholds/seed.py` siembra sus cortes
    con `model_variant='uncalibrated'`, que es la declaración honesta de «estos
    cutoffs son US-GAAP y aquí se aplican sin recalibrar».

    **Por qué se deriva ahora y no antes.** Hasta PHASE-44.8 no había evidencia
    que consultar, así que la alternativa a `GAAP` era adivinar. Y hasta
    PHASE-44.9 los runs no persistían `thresholds_used`, así que mover la
    etiqueta habría hecho irreproducibles los análisis viejos. Con las dos
    piezas puestas, dejar el `GAAP` fijo pasó de ser prudencia a ser una mina:
    el día que alguien admita `20-F` en `annual.ANNUAL_FORMS`, unas cuentas
    IFRS se juzgarían con cortes US-GAAP **sin que nada lo dijera**.

    Todo lo demás es `GAAP`: quien presenta 10-K lo hace en US-GAAP por
    definición, y un valor sin CIK no llega hasta aquí (el alta `ext:` fija su
    norma por separado).
    """
    if analysis_status == AnalysisStatus.NON_GAAP.value:
        return AccountingStd.IFRS
    return AccountingStd.GAAP


def status_from_evidence(
    *,
    cik: str | None,
    annual_report_count: int | None,
    foreign_annual_report_count: int | None = None,
) -> str | None:
    """Traduce lo que el adapter contó en el valor a persistir, o `None`.

    `None` = no comprobado, y se guarda como NULL: es distinto de «comprobado y
    no hay». La distinción importa porque un fallo de red al contar no debe
    marcar un valor como no analizable para siempre.

    Los tres ceros no son el mismo cero, y esto es lo que decide qué se le dice
    al usuario (recuentos verificados contra la SEC):

    - MCD, 33 diez-kás → `ok`.
    - SPY, ni 10-K ni 20-F → `no_annual`: es un vehículo, no una empresa.
    - SAN, 0 diez-kás y 25 veintiefes → `non_gaap`. Publica cuentas anuales
      perfectamente; lo que falta es el mapa IFRS. Decirle a alguien que
      Santander "no publica cuentas" sería falso.

    Args:
        cik: Central Index Key, o `None` para un valor no-US.
        annual_report_count: número de 10-K, o `None` si no se comprobó.
        foreign_annual_report_count: número de 20-F, o `None` si no se comprobó.

    Returns:
        El valor para `securities.analysis_status`, o `None` si no hay evidencia.
    """
    if not cik:
        return AnalysisStatus.NOT_SUPPORTED.value
    if annual_report_count is None:
        return None
    if annual_report_count > 0:
        return AnalysisStatus.OK.value
    if foreign_annual_report_count:
        return AnalysisStatus.NON_GAAP.value
    return AnalysisStatus.NO_ANNUAL.value
