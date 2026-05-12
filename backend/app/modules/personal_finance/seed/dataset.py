"""Dataset de categorías y reglas recomendadas (PHASE-20).

Diseñado para bancos españoles (BBVA, Santander, Sabadell, ING,
Caixabank, Unicaja, Cajamar). Los patrones cubren conceptos típicos
del extracto + comercios habituales en España.

El matching es case + acento-insensible (normalize en repository),
así que los patterns se escriben en MAYÚSCULAS sin acentos para
facilitar la lectura.

Los `priority` siguen esta convención:
- 10-29 → reglas muy específicas (Amazon Prime > Amazon, Abono Nómina).
- 30-49 → reglas sobre concepto del banco (concept). El concepto que
          devuelve el banco es más fiable que el comercio para
          desambiguar (p. ej. concept="PAGO TARJETA - RESTAURANTES" +
          description="Mercadona" → debe ser Restaurantes).
- 50-79 → reglas sobre description (comercios habituales).
- 80+   → reglas genéricas (PAYPAL, TRANSFERENCIAS sin contexto).

Las reglas custom del usuario tienen `priority=100` por defecto, así
que con 10-79 tienen prioridad sobre las que el usuario añada después
(salvo que las baje explícitamente).
"""

from __future__ import annotations

from typing import TypedDict

from app.modules.personal_finance.categories.models import CategoryKind
from app.modules.personal_finance.category_rules.models import (
    RuleField,
    RuleMatchType,
)


class SeedRuleDef(TypedDict):
    pattern: str
    match_type: RuleMatchType
    field: RuleField
    priority: int


class SeedCategoryDef(TypedDict):
    name: str
    kind: CategoryKind
    color: str  # hex #RRGGBB
    icon: str  # emoji
    rules: list[SeedRuleDef]


# Helpers para reducir verbosidad.
def _c(p: str, prio: int = 60) -> SeedRuleDef:
    """Regla CONTAINS sobre ambos campos."""
    return {
        "pattern": p,
        "match_type": RuleMatchType.CONTAINS,
        "field": RuleField.BOTH,
        "priority": prio,
    }


def _cd(p: str, prio: int = 60) -> SeedRuleDef:
    """Regla CONTAINS sobre description únicamente. Default 60."""
    return {
        "pattern": p,
        "match_type": RuleMatchType.CONTAINS,
        "field": RuleField.DESCRIPTION,
        "priority": prio,
    }


def _cc(p: str, prio: int = 40) -> SeedRuleDef:
    """Regla CONTAINS sobre concepto únicamente. Default 40 (gana sobre
    description en caso de ambigüedad — el concepto del banco es más
    fiable que el comercio)."""
    return {
        "pattern": p,
        "match_type": RuleMatchType.CONTAINS,
        "field": RuleField.CONCEPT,
        "priority": prio,
    }


SEED_CATEGORIES: list[SeedCategoryDef] = [
    {
        "name": "Restaurantes",
        "kind": CategoryKind.EXPENSE,
        "color": "#ef4444",
        "icon": "🍽️",
        "rules": [
            _cc("RESTAURANTE"),
            _cc("RESTAURACION"),
            _cd("MCDONALDS"),
            _cd("BURGER KING"),
            _cd("TELEPIZZA"),
            _cd("DOMINO"),
            _cd("KFC"),
            _cd("STARBUCKS"),
            _cd("PAD THAI"),
            _cd("FOSTERS HOLLYWOOD"),
            _cd("VIPS"),
            _cd("LA TAGLIATELLA"),
            _cd("GINOS"),
            _cd("100 MONTADITOS"),
            _cd("GLOVO"),
            _cd("UBER EATS"),
            _cd("JUST EAT"),
            _cd("DELIVEROO"),
        ],
    },
    {
        "name": "Supermercado",
        "kind": CategoryKind.EXPENSE,
        "color": "#22c55e",
        "icon": "🛒",
        "rules": [
            _cc("SUPERMERCADO"),
            _cc("SUPERMERCADOS"),
            _cd("MERCADONA"),
            _cd("CARREFOUR"),
            _cd("LIDL"),
            _cd("ALDI"),
            _cd("DIA"),
            _cd("EROSKI"),
            _cd("ALCAMPO"),
            _cd("HIPERCOR"),
            _cd("CONSUM"),
            _cd("HIPERCASH"),
            _cd("FAMILIA"),
            _cd("UPPER"),
            _cd("MASYMAS"),
        ],
    },
    {
        "name": "Combustible",
        "kind": CategoryKind.EXPENSE,
        "color": "#f97316",
        "icon": "⛽",
        "rules": [
            _cc("GASOLINERA"),
            _cc("GASOLINERAS"),
            _cc("CARBURANTE"),
            _cd("REPSOL"),
            _cd("CEPSA"),
            _cd("BP "),  # espacio para no matchear con BPI etc
            _cd("GALP"),
            _cd("SHELL"),
            _cd("PETRONOR"),
            _cd("E.S. "),  # estaciones de servicio típicas
            _cd("COMBUSTIBLES"),
        ],
    },
    {
        "name": "Transporte",
        "kind": CategoryKind.EXPENSE,
        "color": "#06b6d4",
        "icon": "🚌",
        "rules": [
            _cc("PEAJE"),
            _cc("APARCAMIENTO"),
            _cc("PARKING"),
            _cd("UBER"),
            _cd("CABIFY"),
            _cd("BOLT"),
            _cd("FREE NOW"),
            _cd("RENFE"),
            _cd("ALSA"),
            _cd("METRO"),
            _cd("EMT"),
            _cd("BLABLACAR"),
        ],
    },
    {
        "name": "Suscripciones",
        "kind": CategoryKind.EXPENSE,
        "color": "#a855f7",
        "icon": "📺",
        "rules": [
            _cc("SUSCRIPCION"),
            _cc("SUSCRIPCIONES"),
            _cd("NETFLIX"),
            _cd("HBO"),
            _cd("HBOMAX"),
            _cd("DISNEY"),
            _cd("DISNEY PLUS"),
            _cd("AMAZON PRIME", 30),  # más específica que AMAZON genérico
            _cd("PRIME VIDEO", 30),
            _cd("SPOTIFY"),
            _cd("APPLE.COM"),
            _cd("APPLE MUSIC"),
            _cd("ICLOUD"),
            _cd("GOOGLE ONE"),
            _cd("YOUTUBE"),
            _cd("MICROSOFT"),
            _cd("OFFICE 365"),
            _cd("ADOBE"),
            _cd("DROPBOX"),
            _cd("LINKEDIN"),
            _cd("CHATGPT"),
            _cd("OPENAI"),
            _cd("BATTLE.NET"),
            _cd("STEAM"),
            _cd("PLAYSTATION"),
            _cd("XBOX"),
            _cd("NINTENDO"),
            _cd("PAYPAL", 80),  # genérico — solo gana si no hay nada más concreto
        ],
    },
    {
        "name": "Salud y farmacia",
        "kind": CategoryKind.EXPENSE,
        "color": "#14b8a6",
        "icon": "💊",
        "rules": [
            _cc("FARMACIA"),
            _cd("CLINICA"),
            _cd("HOSPITAL"),
            _cd("DENTISTA"),
            _cd("OPTICA"),
            _cd("DROGUERIA"),
            _cd("DROGUERIAS"),
            _cd("PERFUMERIA"),
            _cd("DOSFARMA"),
            _cd("NATURITAS"),
            _cd("SANAREVA"),
        ],
    },
    {
        "name": "Ocio",
        "kind": CategoryKind.EXPENSE,
        "color": "#ec4899",
        "icon": "🎬",
        "rules": [
            _cc("ESPECTACULO"),
            _cc("ESPECTACULOS"),
            _cd("CINESA"),
            _cd("YELMO"),
            _cd("NEOCINE"),
            _cd("CINES"),
            _cd("TEATRO"),
            _cd("CONCIERTO"),
            _cd("ENTRADAS.COM"),
            _cd("TICKETMASTER"),
            _cd("BOOKING"),
            _cd("AIRBNB"),
            _cd("EXPEDIA"),
            _cd("EDREAMS"),
            _cd("RYANAIR"),
            _cd("VUELING"),
            _cd("IBERIA"),
            _cd("AIR EUROPA"),
        ],
    },
    {
        "name": "Hogar y suministros",
        "kind": CategoryKind.EXPENSE,
        "color": "#eab308",
        "icon": "🏠",
        "rules": [
            _cd("IBERDROLA"),
            _cd("ENDESA"),
            _cd("NATURGY"),
            _cd("REPSOL LUZ"),
            _cd("HOLALUZ"),
            _cd("AGUAS"),
            _cd("CANAL DE ISABEL"),
            _cd("MOVISTAR"),
            _cd("VODAFONE"),
            _cd("ORANGE"),
            _cd("MASMOVIL"),
            _cd("YOIGO"),
            _cd("FINETWORK"),
            _cd("PEPEPHONE"),
            _cd("LOWI"),
            _cd("DIGI"),
            _cd("TELECOM"),
            _cd("LEROY MERLIN"),
            _cd("IKEA"),
            _cd("BAUHAUS"),
            _cd("BRICOR"),
            _cd("BRICOMART"),
        ],
    },
    {
        "name": "Compras online",
        "kind": CategoryKind.EXPENSE,
        "color": "#6366f1",
        "icon": "📦",
        "rules": [
            _cd("AMAZON.ES", 70),
            _cd("WWW.AMAZON", 70),
            _cd("AMAZON ", 70),
            _cd("ALIEXPRESS"),
            _cd("EBAY"),
            _cd("ZALANDO"),
            _cd("ASOS"),
            _cd("PCCOMPONENTES"),
            _cd("MEDIAMARKT"),
            _cd("EL CORTE INGLES"),
            _cd("ZARA"),
            _cd("DECATHLON"),
        ],
    },
    {
        "name": "Grandes superficies",
        "kind": CategoryKind.EXPENSE,
        "color": "#8b5cf6",
        "icon": "🏬",
        "rules": [
            _cc("GRANDES SUPERFICIES"),
            _cd("CARREFOUR ", 60),  # con espacio: solo el genérico, no Express
        ],
    },
    {
        "name": "Bizum recibido",
        "kind": CategoryKind.INCOME,
        "color": "#10b981",
        "icon": "💸",
        "rules": [
            _cc("BIZUM RECIBIDO"),
        ],
    },
    {
        "name": "Bizum enviado",
        "kind": CategoryKind.EXPENSE,
        "color": "#f43f5e",
        "icon": "💸",
        "rules": [
            _cc("BIZUM ENVIADO"),
            _cc("BIZUM COMPRA"),
        ],
    },
    {
        "name": "Nómina",
        "kind": CategoryKind.INCOME,
        "color": "#16a34a",
        "icon": "💰",
        "rules": [
            _cc("NOMINA", 30),
            _cc("ABONO DE NOMINA", 20),
            _cc("ABONO NOMINA", 20),
            _cc("PENSION"),
        ],
    },
    {
        "name": "Transferencias",
        "kind": CategoryKind.EXPENSE,
        "color": "#64748b",
        "icon": "↔️",
        "rules": [
            _cc("TRANSFERENCIA", 80),
            _cc("TRANSFERENCIAS", 80),
            _cc("ORDENES PAGO", 80),
            _cc("ORDEN DE PAGO", 80),
        ],
    },
    {
        "name": "Préstamos e hipotecas",
        "kind": CategoryKind.EXPENSE,
        "color": "#475569",
        "icon": "🏦",
        "rules": [
            _cc("PRESTAMO", 30),
            _cc("HIPOTECA", 30),
            _cc("AMORTIZACION", 30),
            _cc("CARGO POR AMORTIZACION"),
            _cc("AMORTIZACION DE PRESTAMO"),
        ],
    },
    {
        "name": "Bancos y comisiones",
        "kind": CategoryKind.EXPENSE,
        "color": "#94a3b8",
        "icon": "💳",
        "rules": [
            _cc("COMISION"),
            _cc("COMISIONES"),
            _cc("MANTENIMIENTO"),
            _cc("CUOTA SERVICIOS"),
            _cc("RET. EFECTIVO"),
            _cc("RETIRADA EFECTIVO"),
            _cc("EFECTIVO/CAJERO"),
            _cc("CAJERO"),
        ],
    },
    {
        "name": "Seguros",
        "kind": CategoryKind.EXPENSE,
        "color": "#0ea5e9",
        "icon": "🛡️",
        "rules": [
            _cc("SEGURO", 60),
            _cc("ADEUDO DE SEGUROS"),
            _cd("MAPFRE"),
            _cd("MUTUA MADRILENA"),
            _cd("AXA"),
            _cd("ALLIANZ"),
            _cd("LINEA DIRECTA"),
            _cd("GENERALI"),
            _cd("REALE"),
        ],
    },
    {
        "name": "Tarjeta de crédito",
        "kind": CategoryKind.EXPENSE,
        "color": "#f59e0b",
        "icon": "💳",
        "rules": [
            _cc("ADEUDO MENSUAL DE TARJETA"),
            _cc("CARGO POR OPERACION FINANCIADA"),
            _cc("OPERACION FINANCIADA CON TARJETA"),
            _cc("TARJETA FINANCIADA"),
        ],
    },
    # PHASE-22: intereses como expense diferenciado del principal.
    # El wizard "Pagar deuda" splittea la cuota entre principal
    # (transfer hacia la liability) y estos intereses (expense).
    {
        "name": "Intereses hipoteca",
        "kind": CategoryKind.EXPENSE,
        "color": "#475569",
        "icon": "🏦",
        "rules": [
            _cc("INTERESES HIPOTECA"),
            _cc("INTERESES HIPOTECARIOS"),
        ],
    },
    {
        "name": "Intereses préstamo",
        "kind": CategoryKind.EXPENSE,
        "color": "#64748b",
        "icon": "💸",
        "rules": [
            _cc("INTERESES PRESTAMO"),
            _cc("LIQUIDACION DE INTERESES"),
        ],
    },
    {
        "name": "Intereses tarjeta",
        "kind": CategoryKind.EXPENSE,
        "color": "#f97316",
        "icon": "💳",
        "rules": [
            _cc("INTERESES TARJETA"),
            _cc("INTERESES POR APLAZAMIENTO"),
            _cc("INTERESES FINANCIACION"),
        ],
    },
]
