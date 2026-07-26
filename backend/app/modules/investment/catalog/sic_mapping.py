"""Mapeo SIC → sector interno (PHASE-44.7, ARCHITECTURE §1, Dec.15).

El código SIC (Standard Industrial Classification) que publica la SEC en el
perfil de cada emisor se traduce a nuestra taxonomía sectorial PROPIA
(`SectorInternal`), que sólo gobierna qué umbrales y modelos aplican — NO es
GICS (licenciado) ni afecta a la contabilidad.

El mapeo es una heurística por rangos con excepciones específicas donde el rango
mezcla sectores dispares (p. ej. dentro de "químicas" 28xx viven las
farmacéuticas, que son healthcare). Ante un SIC desconocido o ausente,
`UNKNOWN` — nunca se inventa un sector, porque el sector arrastra los umbrales.

`is_financial` y `is_reit` NO se derivan aquí: los decide el adapter EDGAR
(`classify_sic` + los metadatos de la librería), que es la fuente de verdad
por-valor. Este mapeo sólo elige el `SectorInternal` para los umbrales.
"""

from __future__ import annotations

from app.modules.investment.enums import SectorInternal

# Códigos SIC concretos cuya traducción no coincide con la de su rango.
_SPECIFIC: dict[int, SectorInternal] = {
    2834: SectorInternal.HEALTHCARE,  # preparaciones farmacéuticas (JNJ)
    2835: SectorInternal.HEALTHCARE,  # diagnósticos in-vitro
    2836: SectorInternal.HEALTHCARE,  # productos biológicos
    3826: SectorInternal.HEALTHCARE,  # instrumentos de laboratorio
    3841: SectorInternal.HEALTHCARE,  # aparatos quirúrgicos y médicos
    3842: SectorInternal.HEALTHCARE,  # suministros ortopédicos
    3843: SectorInternal.HEALTHCARE,  # equipamiento dental
    3845: SectorInternal.HEALTHCARE,  # electromedicina
    5912: SectorInternal.CONSUMER_STAPLES,  # farmacias (droguerías)
    6798: SectorInternal.REAL_ESTATE,  # REIT (aunque 67xx sea holding financiero)
    7372: SectorInternal.TECHNOLOGY,  # software empaquetado
}


def sic_to_sector(sic: str | None) -> SectorInternal:
    """Traduce un código SIC a `SectorInternal`. Sin SIC (o no numérico) →
    `UNKNOWN` (que arrastra los umbrales genéricos, nunca una calibración
    inventada)."""
    if not sic:
        return SectorInternal.UNKNOWN
    try:
        code = int(sic.strip())
    except (ValueError, AttributeError):
        return SectorInternal.UNKNOWN

    if code in _SPECIFIC:
        return _SPECIFIC[code]

    # Rangos por división SIC (con los desgloses relevantes primero).
    if 100 <= code <= 999:  # agricultura, silvicultura, pesca
        return SectorInternal.MATERIALS
    if 1000 <= code <= 1099:  # minería de metales
        return SectorInternal.MATERIALS
    if 1200 <= code <= 1399:  # carbón + petróleo y gas
        return SectorInternal.ENERGY
    if 1400 <= code <= 1499:  # minerales no metálicos
        return SectorInternal.MATERIALS
    if 1500 <= code <= 1799:  # construcción
        return SectorInternal.INDUSTRIALS
    if 2000 <= code <= 2199:  # alimentación y tabaco
        return SectorInternal.CONSUMER_STAPLES
    if 2200 <= code <= 2399:  # textil y confección
        return SectorInternal.CONSUMER_DISCRETIONARY
    if 2400 <= code <= 2499:  # madera
        return SectorInternal.MATERIALS
    if 2500 <= code <= 2599:  # mobiliario
        return SectorInternal.CONSUMER_DISCRETIONARY
    if 2600 <= code <= 2699:  # papel
        return SectorInternal.MATERIALS
    if 2700 <= code <= 2799:  # imprenta y edición
        return SectorInternal.COMMUNICATION
    if 2800 <= code <= 2899:  # químicas (las farma ya salieron por _SPECIFIC)
        return SectorInternal.MATERIALS
    if 2900 <= code <= 2999:  # refino de petróleo
        return SectorInternal.ENERGY
    if 3570 <= code <= 3579 or 3670 <= code <= 3699:  # ordenadores y electrónica
        return SectorInternal.TECHNOLOGY
    if 3000 <= code <= 3999:  # resto de manufactura
        return SectorInternal.INDUSTRIALS
    if 4000 <= code <= 4799:  # transporte
        return SectorInternal.INDUSTRIALS
    if 4800 <= code <= 4899:  # comunicaciones
        return SectorInternal.COMMUNICATION
    if 4900 <= code <= 4999:  # utilities
        return SectorInternal.UTILITIES
    if 5000 <= code <= 5199:  # comercio al por mayor
        return SectorInternal.CONSUMER_DISCRETIONARY
    if 5400 <= code <= 5499:  # tiendas de alimentación
        return SectorInternal.CONSUMER_STAPLES
    if 5200 <= code <= 5999:  # resto del comercio minorista (incl. 5812 restaurantes)
        return SectorInternal.CONSUMER_DISCRETIONARY
    if 6000 <= code <= 6499:  # banca, crédito, valores, seguros
        return SectorInternal.FINANCIALS
    if 6500 <= code <= 6599:  # inmobiliario
        return SectorInternal.REAL_ESTATE
    if 6700 <= code <= 6799:  # holdings e inversión (6798 REIT ya salió)
        return SectorInternal.FINANCIALS
    if 7370 <= code <= 7379:  # servicios informáticos y software
        return SectorInternal.TECHNOLOGY
    if 7800 <= code <= 7999:  # ocio y entretenimiento
        return SectorInternal.COMMUNICATION
    if 8000 <= code <= 8099:  # servicios sanitarios
        return SectorInternal.HEALTHCARE
    if 7000 <= code <= 8999:  # resto de servicios
        return SectorInternal.CONSUMER_DISCRETIONARY

    return SectorInternal.UNKNOWN
