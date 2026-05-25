"""PHASE-30.2 — Módulo de deuda en dos capas.

Capa 1: KPIs derivados del flujo de transacciones categorizadas como
deuda (`/debt/category-summary`). No requiere onboarding de
liabilities, basta con que el usuario categorice sus pagos.

Capa 2: enriquecimiento opcional con liability accounts (saldo
pendiente, cuadro de amortización). Vive en `accounts/` durante
PHASE-30.x — este módulo sólo aporta la capa flujo.
"""
