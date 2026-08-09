"""Calibración sectorial de los umbrales (PHASE-44.21).

Un ratio no significa lo mismo en una eléctrica que en una tecnológica. Una
utility con deuda neta 4× EBITDA es normal —caja regulada, activos de cuarenta
años—; una tecnológica con 4× está en problemas. Hasta ahora el motor aplicaba
UNA sola vara a todas, así que media docena de semáforos de un sector regulado
salían en rojo permanente: un rojo que no informa se aprende a ignorar, y
entonces deja de informar también el que sí importa.

**Qué hay aquí y qué no.** Esto son *perfiles* del motor de acciones, no motores
nuevos. El motor bancario completo (NIM, CET1, morosidad, LCR) exige un canónico
ampliado y queda fuera: en financieras lo que se hace es **apagar** lo que no
tiene sentido y re-bandear las tres que sí (R5, R6 y S3 como proxy de capital),
diciéndolo en pantalla.

**Por qué vive en el ENGINE y no sólo en la tabla.** `scoring_thresholds` guarda
la calibración para que un run pueda explicar con qué vara se midió
(`thresholds_used`, PHASE-44.9). Pero si la aplicabilidad viviera SÓLO ahí, una
base recién creada —o una fila que nadie sembró— devolvería el catálogo genérico
y juzgaría a un banco con cortes industriales sin decir nada. Es exactamente lo
que le pasó a la exención de S7 en PHASE-44.18: razonada, documentada e
**inerte** durante ocho fases porque dependía de una fila que no existía. Aquí el
engine resuelve el perfil por su cuenta y el seed REFLEJA lo que el engine
resuelve, así que las dos no pueden divergir.

**Regla anti-tuning.** Jamás se ajusta una banda para que salga verde una
posición propia. Las bandas se calibran con fuentes, se versionan (el hash de
`thresholds_version`) y se revisan con runs reales.

Vocabulario: el documento de calibración habla de `TELECOM`, `REAL_ESTATE_REIT` y
`GENERIC`; el enum persistido (`SectorInternal`, PHASE-44.1) los llama
`COMMUNICATION`, `REAL_ESTATE` y `UNKNOWN`. Se usa el del enum —renombrar un tipo
Postgres para ganar sinónimos no es un cambio, es una migración— y `sic_mapping`
deja `COMMUNICATION` con los SIC 4800-4899, que son telecomunicaciones: sin eso,
las bandas de telecom caerían también sobre editoriales y ocio.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from decimal import Decimal

from app.modules.investment.analysis.engine import base_ratios
from app.modules.investment.analysis.engine.catalog import (
    ALL_DEFAULT_THRESHOLDS,
    definition_for,
)
from app.modules.investment.analysis.engine.flag_rules import (
    FIN_CASH_REASON,
    FIN_COVERAGE_REASON,
    FIN_WORKING_CAPITAL_REASON,
    NO_INVENTORY_REASON,
)
from app.modules.investment.analysis.engine.types import ThresholdSpec
from app.modules.investment.enums import AccountingStd, SectorInternal, ThresholdDirection

UNCALIBRATED = "uncalibrated"
"""`model_variant` para IFRS/PGC: los cortes son US-GAAP, sin recalibrar."""

BANK_CAPITAL_PROXY = "bank_capital_proxy"
"""`model_variant` de S3 en financieras: patrimonio sobre activo es un PROXY
contable del capital, no el capital regulatorio (CET1), y la pantalla lo dice."""


def _d(value: str) -> Decimal:
    return Decimal(value)


class _Shape(enum.StrEnum):
    """La forma de un corte, atada a la `direction` de la métrica."""

    HIGHER = "higher"
    LOWER = "lower"
    CENTRAL = "central"


@dataclass(frozen=True)
class Cuts:
    """Los cortes de una banda sectorial, con su forma declarada.

    La forma existe para que un delta escrito con la geometría equivocada falle
    al arrancar en vez de invertir un semáforo en silencio: en `higher_better`
    los cortes son el suelo (alarma, ok) y en `lower_better` el techo (ok,
    alarma), así que los mismos dos números significan lo contrario.
    """

    shape: _Shape
    low_alarm: Decimal | None = None
    low_ok: Decimal | None = None
    high_ok: Decimal | None = None
    high_alarm: Decimal | None = None


def higher(alarm: str, ok: str) -> Cuts:
    """Más es mejor: por debajo de `alarm` rojo, por debajo de `ok` ámbar."""
    return Cuts(shape=_Shape.HIGHER, low_alarm=_d(alarm), low_ok=_d(ok))


def lower(ok: str, alarm: str) -> Cuts:
    """Menos es mejor: por encima de `alarm` rojo, por encima de `ok` ámbar."""
    return Cuts(shape=_Shape.LOWER, high_ok=_d(ok), high_alarm=_d(alarm))


def central(low_alarm: str, low_ok: str, high_ok: str, high_alarm: str) -> Cuts:
    """Banda central: fuera de las alarmas rojo, dentro de los ok verde."""
    return Cuts(
        shape=_Shape.CENTRAL,
        low_alarm=_d(low_alarm),
        low_ok=_d(low_ok),
        high_ok=_d(high_ok),
        high_alarm=_d(high_alarm),
    )


_SHAPE_OF_DIRECTION: Mapping[ThresholdDirection, _Shape] = {
    ThresholdDirection.HIGHER_BETTER: _Shape.HIGHER,
    ThresholdDirection.LOWER_BETTER: _Shape.LOWER,
    ThresholdDirection.BAND: _Shape.CENTRAL,
}


@dataclass(frozen=True)
class SectorProfile:
    """Los DELTAS de un sector sobre la banda genérica.

    Sólo se escribe lo que difiere. Lo que no aparece se hereda del catálogo del
    engine, que es el perfil `GENERIC` del documento de calibración: así una
    métrica nueva entra a la vez en todos los sectores y no hay doce copias que
    mantener sincronizadas.
    """

    overrides: Mapping[str, Cuts] = field(default_factory=dict)
    not_applicable: Mapping[str, str] = field(default_factory=dict)
    """`metric_key` → por qué no aplica, en español. La razón viaja al run y la
    pantalla la enseña: un «N/A» mudo es indistinguible de un fallo."""
    variants: Mapping[str, str] = field(default_factory=dict)
    """`metric_key` → `model_variant`, para las bandas que se aplican pero
    necesitan una advertencia (S3 como proxy de capital bancario)."""


RELATIVE_CUTS: Mapping[str, str] = {
    "S6": "S2",
    "L2": "L1",
}
"""Métricas cuyo delta sectorial se DERIVA del de su hermana en vez de escribirse.

S6 (cobertura de intereses por caja) es S2 medida con caja en lugar de con EBIT,
y L2 (prueba ácida) es L1 sin inventario: si un sector mueve una y no la otra,
las dos dejan de contar la misma historia sobre la misma empresa. Se escala por
el mismo factor y se redondea a dos decimales — mecánico y reproducible, en vez
de una segunda tabla escrita a mano que envejece por su cuenta.
"""


# ── Motivos ───────────────────────────────────────────────────────────

_NO_INVENTORY = NO_INVENTORY_REASON
_FIN_CASH = FIN_CASH_REASON
_FIN_WC = FIN_WORKING_CAPITAL_REASON
_FIN_COVERAGE = FIN_COVERAGE_REASON
_FIN_LEVERAGE = base_ratios.FINANCIAL_LEVERAGE_REASON
"""El motivo del apalancamiento bancario lo posee `base_ratios`, que aplica ese
suelo aunque nadie resuelva un perfil. Se importa en vez de repetirse: dos copias
de la misma frase acaban diciendo cosas distintas."""

_FIN_EBITDA = "el EBITDA carece de sentido en banca: no describe la economía del negocio"
_FIN_LIQUIDITY = (
    "la liquidez bancaria se mide con LCR y NSFR, que no están en el canónico de "
    "un 10-K: el circulante de un banco no es comparable al de una fábrica"
)
_FIN_INVESTED = "el capital invertido no modela un balance bancario"
_FIN_MODEL = (
    "el modelo se calibró sobre empresas no financieras y no se ha recalibrado "
    "para banca: aplicarlo daría alarmas constantes sin significado"
)

FINANCIALS_NOT_APPLICABLE: Mapping[str, str] = {
    # Caja libre y EBITDA
    "Q2": _FIN_CASH,
    "Q3": _FIN_CASH,
    "D2": _FIN_CASH,
    "D3": _FIN_CASH,
    "D4": _FIN_CASH,
    "D5": _FIN_CASH,
    "D8": _FIN_CASH,
    "D6": "sólo aplica a socimis",
    "R7": _FIN_CASH,
    "S4": _FIN_EBITDA,
    "S4b": _FIN_EBITDA,
    "S5": _FIN_CASH,
    "B3": _FIN_CASH,
    # Cobertura de intereses
    "S2": _FIN_COVERAGE,
    "S6": _FIN_COVERAGE,
    # Apalancamiento. S8 (qué parte de la deuda vence a menos de un año) NO se
    # apaga: significa lo mismo en un banco que en una fábrica, y el documento de
    # calibración tampoco la lista.
    "S1": _FIN_LEVERAGE,
    "S7": _FIN_LEVERAGE,
    # Liquidez
    "L1": _FIN_LIQUIDITY,
    "L2": _FIN_LIQUIDITY,
    "L3": _FIN_LIQUIDITY,
    "L4": _FIN_LIQUIDITY,
    # Actividad: el circulante de un banco no es capital de trabajo
    "A1": _FIN_WC,
    "A2": _FIN_WC,
    "A3": _FIN_WC,
    "A4": _FIN_WC,
    "A5": _FIN_WC,
    # Retorno sobre capital invertido
    "R9": _FIN_INVESTED,
    "R9b": _FIN_INVESTED,
    "R10": "un banco no tiene coste de ventas, así que el beneficio bruto no existe",
    # Modelos forenses
    "m_score": _FIN_MODEL,
    "z_score": _FIN_MODEL,
    "f_score": _FIN_MODEL,
    "accruals": _FIN_MODEL,
    "F5": _FIN_MODEL,
    "F6": _FIN_MODEL,
    "FZ": _FIN_MODEL,
    "F7": _FIN_MODEL,
}
"""Qué se apaga en una financiera y por qué (documento de calibración §5).

Lo que sobrevive —y es deliberado, no un olvido— es el núcleo del juicio bancario
que SÍ se sostiene con un 10-K: R5 (ROE), R6 con banda bancaria, S3 como proxy de
capital, D1 (payout sobre beneficio), la trayectoria del dividendo (T2/T3), la
calidad del beneficio que es medible (Q1, Q5, Q4) y B4, que compara el dividendo
con el beneficio y no con la caja libre.

Sólo se listan claves de MÉTRICA. Las reglas de bandera van en
`flags_not_applicable`: no tienen fila de umbral, así que ponerlas aquí sería
escribir una exención que nadie lee — el defecto de PHASE-44.18 otra vez.
"""

# ── Los perfiles ──────────────────────────────────────────────────────
#
# Anclas de la calibración v1 en `improvements/sector-calibration-investment.md`
# §4. Cada delta tiene una razón editorial detrás; los que no la tienen, no
# están — un sector sin perfil hereda el genérico, que es una decisión tan
# explícita como las otras.

_ASSET_HEAVY_GP = higher("0.08", "0.15")
"""R10 (Novy-Marx) en negocios intensivos en activo. El 0,33 genérico sale del
paper original sobre el mercado amplio estadounidense, donde el denominador es un
activo mucho más ligero: aplicárselo a una red eléctrica mide el sector, no la
empresa."""

SECTOR_PROFILES: Mapping[SectorInternal, SectorProfile] = {
    SectorInternal.UTILITIES: SectorProfile(
        overrides={
            # Mediana de grado de inversión del sector 5,1×; por encima de 4× es
            # comercialmente normal en reguladas.
            "S4": lower("4", "5.5"),
            "S4b": lower("5.5", "7"),
            # Caja regulada y estable: soporta una cobertura menor.
            "S2": higher("2", "3.5"),
            # Estructura regulada, más apalancada por diseño.
            "S1": lower("0.7", "0.8"),
            # Liquidez estructuralmente baja: su riesgo real es refinanciar, y de
            # eso se ocupa L4.
            "L1": higher("0.7", "1.0"),
            "R6": higher("0.015", "0.035"),
            # Retorno regulado ≈ retorno permitido.
            "R9": higher("0.05", "0.07"),
            "R9b": higher("0.03", "0.05"),
            "R10": _ASSET_HEAVY_GP,
            # Payout alto ES el modelo del sector. La banda alta NO relaja C7 ni
            # B4: un dividendo por encima de la caja libre financiado con deuda
            # sigue siendo rojo, y la utility que lo hace de forma crónica es
            # exactamente el caso que C7 existe para cazar.
            "D2": lower("0.75", "0.95"),
        },
        not_applicable={"A2": _NO_INVENTORY},
    ),
    SectorInternal.COMMUNICATION: SectorProfile(
        overrides={
            "S4": lower("2.5", "4"),
            "S4b": lower("4", "5.5"),
            # Ingresos por suscripción: previsibles, aguantan menos cobertura.
            "S2": higher("2.5", "4"),
            "L1": higher("0.7", "1.0"),
            "R10": _ASSET_HEAVY_GP,
        },
        not_applicable={"A2": _NO_INVENTORY},
    ),
    SectorInternal.ENERGY: SectorProfile(
        overrides={
            # Cíclico: el apalancamiento debe ser BAJO precisamente porque el
            # EBITDA del denominador es el del punto del ciclo que no conoces.
            "S4": lower("1.5", "2.5"),
            "S4b": lower("2", "3.5"),
            "R10": _ASSET_HEAVY_GP,
        },
    ),
    SectorInternal.MATERIALS: SectorProfile(
        overrides={"S4": lower("2", "3"), "R10": _ASSET_HEAVY_GP},
    ),
    SectorInternal.CONSUMER_STAPLES: SectorProfile(
        overrides={
            "S4": lower("2.5", "3.5"),
            # Circulante negativo (cobra antes de pagar) es lo normal en
            # distribución: ver la regla cruzada RC-1 en `base_ratios`.
            "L1": higher("0.8", "1.2"),
            "D2": lower("0.70", "0.90"),
        },
    ),
    SectorInternal.CONSUMER_DISCRETIONARY: SectorProfile(
        overrides={"L1": higher("0.8", "1.2")},
    ),
    SectorInternal.HEALTHCARE: SectorProfile(
        overrides={
            "S4": lower("2.5", "3.5"),
            "R10": higher("0.30", "0.45"),
            # Compradores en serie estructurales: el fondo de comercio alto es su
            # modelo, no una anomalía por sí solo.
            "F5": lower("0.40", "0.60"),
        },
    ),
    SectorInternal.TECHNOLOGY: SectorProfile(
        overrides={
            # Asset-light: rara vez por encima de 2×, y la caja neta es lo típico.
            "S4": lower("1", "2"),
            "S4b": lower("1.5", "3"),
            # Sin excusa para una cobertura baja.
            "S2": higher("5", "10"),
            "R10": higher("0.30", "0.45"),
            "F5": lower("0.40", "0.60"),
        },
        not_applicable={"A2": _NO_INVENTORY},
    ),
    SectorInternal.REAL_ESTATE: SectorProfile(
        overrides={
            # El sector opera a 5-7× y la media de REIT de oficinas está en 8,5×.
            # El juicio principal de una socimi es D6 sobre FFO, no S4.
            "S4": lower("6", "8"),
            "S4b": lower("7.5", "9.5"),
            "S2": higher("1.8", "2.5"),
            "R10": _ASSET_HEAVY_GP,
            "D6": lower("0.80", "0.95"),
        },
        not_applicable={
            "A2": _NO_INVENTORY,
            "accruals": (
                "la amortización del inmueble domina los devengos de una socimi: "
                "el modelo de Sloan mediría contabilidad inmobiliaria, no manipulación. "
                "El juicio va por el payout sobre FFO (D6)"
            ),
        },
    ),
    SectorInternal.FINANCIALS: SectorProfile(
        overrides={
            # La banda bancaria: un banco con ROA del 1% es un buen banco.
            "R6": higher("0.007", "0.012"),
            # Patrimonio sobre activo como proxy de capital.
            "S3": higher("0.05", "0.08"),
            # El dividendo bancario se juzga sobre beneficio (y sobre el
            # supervisor), así que D1 pasa a ser LA métrica.
            "D1": lower("0.50", "0.70"),
        },
        not_applicable=FINANCIALS_NOT_APPLICABLE,
        variants={"S3": BANK_CAPITAL_PROXY},
    ),
}

# ── Resolución ────────────────────────────────────────────────────────


def _with_cuts(spec: ThresholdSpec, cuts: Cuts) -> ThresholdSpec:
    expected = _SHAPE_OF_DIRECTION[spec.direction]
    if cuts.shape is not expected:
        raise ValueError(
            f"{spec.metric_key}: el delta sectorial se escribió como '{cuts.shape}' y la "
            f"métrica es '{spec.direction}' — los mismos dos números significan lo contrario"
        )
    return replace(
        spec,
        low_alarm=cuts.low_alarm,
        low_ok=cuts.low_ok,
        high_ok=cuts.high_ok,
        high_alarm=cuts.high_alarm,
    )


def _scale(base: Decimal | None, factor: Decimal | None) -> Decimal | None:
    if base is None or factor is None:
        return None
    return (base * factor).quantize(Decimal("0.01"))


def _factor(sector_value: Decimal | None, generic_value: Decimal | None) -> Decimal | None:
    if sector_value is None or generic_value is None or generic_value == 0:
        return None
    return sector_value / generic_value


def _derived_cuts(target: str, source: str, overrides: Mapping[str, Cuts]) -> Cuts | None:
    """El delta de `target` escalado desde el de `source` (`RELATIVE_CUTS`)."""
    source_cuts = overrides.get(source)
    generic_source = ALL_DEFAULT_THRESHOLDS.get(source)
    generic_target = ALL_DEFAULT_THRESHOLDS.get(target)
    if source_cuts is None or generic_source is None or generic_target is None:
        return None
    return Cuts(
        shape=source_cuts.shape,
        low_alarm=_scale(
            generic_target.low_alarm, _factor(source_cuts.low_alarm, generic_source.low_alarm)
        ),
        low_ok=_scale(generic_target.low_ok, _factor(source_cuts.low_ok, generic_source.low_ok)),
        high_ok=_scale(
            generic_target.high_ok, _factor(source_cuts.high_ok, generic_source.high_ok)
        ),
        high_alarm=_scale(
            generic_target.high_alarm, _factor(source_cuts.high_alarm, generic_source.high_alarm)
        ),
    )


def profile_for(sector: SectorInternal, *, is_financial: bool = False) -> SectorProfile:
    """El perfil efectivo de un valor.

    `is_financial` es una propiedad del VALOR, no del sector: un holding
    clasificado en otro sitio puede serlo, y entonces manda el perfil financiero
    por encima del de su sector. La fuente de verdad de ese flag es
    `securities.is_financial`, que fija el adapter.
    """
    profile = SECTOR_PROFILES.get(sector, SectorProfile())
    if not is_financial or sector is SectorInternal.FINANCIALS:
        return profile
    financial = SECTOR_PROFILES[SectorInternal.FINANCIALS]
    return SectorProfile(
        overrides={**profile.overrides, **financial.overrides},
        not_applicable={**profile.not_applicable, **financial.not_applicable},
        variants={**profile.variants, **financial.variants},
    )


def _resolvable_specs(profile: SectorProfile) -> dict[str, ThresholdSpec]:
    """Las métricas con banda, MÁS las que este perfil apaga aunque no la tengan.

    A2 (días de inventario) no tiene banda absoluta —un DIO de 45 días es
    excelente en distribución y pésimo en software—, así que no está en
    `ALL_DEFAULT_THRESHOLDS` y su exención sectorial no tendría dónde viajar. Sin
    esto, la pantalla de una eléctrica diría de A2 «sin banda absoluta: se juzga
    por deriva», cuando lo cierto es que ese negocio no tiene inventario que
    rotar. Se le fabrica un umbral SIN cortes: `applies=False` hace que
    `band_for` devuelva `None` antes de mirarlos.
    """
    specs = dict(ALL_DEFAULT_THRESHOLDS)
    for key in profile.not_applicable:
        if key in specs:
            continue
        if definition_for(key) is None:
            raise ValueError(
                f"el perfil sectorial apaga '{key}', que no está en el catálogo del engine"
            )
        specs[key] = ThresholdSpec(metric_key=key, direction=ThresholdDirection.BAND)
    return specs


def resolve_thresholds(
    sector: SectorInternal,
    accounting_std: AccountingStd,
    *,
    is_financial: bool = False,
) -> dict[str, ThresholdSpec]:
    """El juego de umbrales efectivo de un (sector × norma).

    Parte del catálogo del engine —el perfil genérico— y le aplica el delta del
    sector.

    La norma contable no toca los cortes: los marca. Unos cortes US-GAAP
    aplicados a cuentas IFRS se aplican igual (no tenemos otros) pero salen con
    `model_variant='uncalibrated'`, para que la pantalla lo declare en vez de
    presentarlos como propios.
    """
    profile = profile_for(sector, is_financial=is_financial)
    resolved: dict[str, ThresholdSpec] = {}
    for key, generic in _resolvable_specs(profile).items():
        spec = generic
        cuts = profile.overrides.get(key)
        if cuts is None and key in RELATIVE_CUTS:
            cuts = _derived_cuts(key, RELATIVE_CUTS[key], profile.overrides)
        if cuts is not None:
            spec = _with_cuts(spec, cuts)
        reason = profile.not_applicable.get(key)
        if reason is not None:
            spec = replace(spec, applies=False, not_applicable_reason=reason)
        variant = profile.variants.get(key)
        if variant is not None:
            spec = replace(spec, model_variant=variant)
        if accounting_std is not AccountingStd.GAAP and spec.model_variant is None:
            spec = replace(spec, model_variant=UNCALIBRATED)
        resolved[key] = spec
    return resolved
