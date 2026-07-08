"""Módulo de analítica derivada de finanzas personales (PHASE-37.3+).

Read-only sobre `transactions`/`categories`/`fixed_expenses`/`accounts`.
Aloja cálculos que combinan varias fuentes del dominio y no encajan en
el dashboard puro:

- `expense-structure` (37.3): gasto estructural vs puntual + tasa de
  ahorro dual, sobre la heurística de recurrencia de `recurrence.py`.
- `month-outlook` (37.4): proyección de fin de mes + runway.
"""
