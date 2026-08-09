"""Catálogo de banderas del engine (PHASE-44.9).

Una `Flag` sólo existe cuando SALTA, y entonces trae su `message` redactado. Pero
la síntesis usa banderas como **señales** de sus cuatro preguntas, y ahí hace
falta nombrarlas también cuando NO han saltado —«se comprobó y no se encendió» es
información, no silencio—. Sin un nombre estático, esas señales viajaban como la
clave cruda y el usuario leía literalmente

    M-Score · B4_dividend_funded_externally

en la pantalla del veredicto.

Aquí vive ese nombre. Es un mapa `key → etiqueta` puro: ni BD, ni reloj, ni red.
El `message` de la bandera encendida sigue siendo la explicación completa; esto
es sólo cómo se llama.
"""

from __future__ import annotations

FLAG_LABELS: dict[str, str] = {
    # ── Cruces evolutivos (capa 1.5) ──────────────────────────────
    "C1_receivables_vs_revenue": "Cobros creciendo por encima de las ventas",
    "C2_income_without_cash": "Beneficio que no se convierte en caja",
    "C3_inventory_vs_cogs": "Inventario creciendo por encima del coste de ventas",
    "C4_underinvestment": "Infrainversión (capex por debajo de la amortización)",
    "C5_goodwill_without_acquisitions": "Fondo de comercio que sube sin compras",
    "C6_dilution": "Dilución sostenida del accionista",
    "C7_shareholder_return_funded_by_debt": "Retorno al accionista financiado con deuda",
    "C8_acquired_growth": "Crecimiento comprado, no orgánico",
    "growth_externally_funded": "Crecimiento por encima de lo autofinanciable",
    # ── Fiscalidad y soporte del dividendo (capa 3) ───────────────
    "Q4_tax_anomaly": "Tipo impositivo anómalo",
    "Q4_tax_persistently_low": "Tipo impositivo persistentemente bajo",
    "B1_debt_competes_with_dividend": "La deuda compite con el dividendo",
    "B2_interest_priority": "Los intereses tienen prioridad sobre el dividendo",
    "B4_dividend_funded_externally": "Dividendo financiado con deuda o emisión",
    # ── Reglas cruzadas sectoriales (PHASE-44.21) ─────────────────
    "RC1_negative_working_capital": "Modelo de circulante negativo (cobra antes de pagar)",
    "RC2_utility_payout_needs_funding_check": "Payout alto en una regulada: mira quién lo financia",
    # ── Calidad del dato (capa 1 y forense) ───────────────────────
    "ebt_divergence": "El resultado antes de impuestos no cuadra con EBIT − intereses",
    "ebt_reconstruction_divergence": "Resultado antes de impuestos reconstruido con divergencia",
    "fcf_divergence": "Las dos formas de medir la caja libre no cuadran",
    "z_score_uncalibrated_for_reit": "Z''-Score sin calibrar para socimis",
}
"""Las claves de bandera que el engine puede emitir, con su nombre legible.

Un test comprueba que el conjunto coincide EXACTAMENTE con las claves que las
seis capas emiten: si alguien añade una bandera sin nombrarla aquí, CI falla en
vez de dejar que la clave cruda llegue a la pantalla."""


def flag_label(key: str) -> str:
    """Nombre legible de una bandera. Cae a la clave si no está catalogada —
    feo pero honesto: mejor la clave que un nombre inventado."""
    return FLAG_LABELS.get(key, key)
