"""Transferencias internas entre cuentas del usuario (PHASE-19.3).

Una transferencia interna es un par de transacciones (una salida en
cuenta A + una entrada en cuenta B) que representan un mismo
movimiento de patrimonio del usuario consigo mismo. NO son ni gasto ni
ingreso desde el punto de vista del flujo neto, así que se excluyen de
los KPIs de cashflow / tasa de ahorro / donut / presupuestos. Sí
afectan al saldo individual de cada cuenta.

Modelo: cada `Transaction` tiene `transfer_pair_id` (FK auto-referente)
que apunta a la otra mitad. Por convención el enlace es bidireccional
— al emparejar A con B, la fila de A apunta a B.id y la de B apunta
a A.id.

Detección: el `matcher` busca pares de txs activas no emparejadas con:
- mismo `amount` exacto
- misma `currency`
- cuentas distintas (`account_id` diferente)
- `occurred_at` dentro de ±N días (DEFAULT_WINDOW_DAYS)
- `kind` opuesto (una income, una expense — el enlace cruzado)
"""
