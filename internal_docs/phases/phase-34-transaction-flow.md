# PHASE-34 — La verdad del dinero vive en la transacción (`flow`)

**Estado**: 🚧 en curso (código completo + verde; pendiente prueba manual del usuario y PR)
**Rama**: `feat/phase-34-transaction-flow`
**PR**: —
**Fecha de merge**: —
**ADR**: [`decisions/0004-transaction-level-money-truth.md`](../decisions/0004-transaction-level-money-truth.md)

## Objetivo

Mover la **fuente de verdad del dinero** (dirección entra/sale +
clasificación gasto/ingreso/transferencia) de la **categoría** a la
**transacción**, mediante la columna `transactions.flow`. Así un error de
categoría deja de costar dinero: sólo cambia el grupo del donut, nunca el
saldo ni el cashflow.

Cierra la familia de bugs PHASE-23.1 / 28 / 32: mientras la categoría fuera
la verdad del dinero, cualquier mecanismo de categorización (regla,
bank-mapping, import) podía producir un bug de dinero con un solo fallo. Se
midieron dos doble-conteos reales (transferencias-como-gasto y liquidación de
tarjeta `ADEUDO` contada como gasto) que inflaban el gasto del usuario hasta
un 76 % en un mes.

## Qué se implementó

`flow` es un enum a nivel de transacción: `IN | OUT | TRANSFER_IN |
TRANSFER_OUT`. `amount` sigue **positivo**; el signo del saldo lo aplica la
query desde `flow` + `account.nature`. El cashflow del mes cuenta
`gasto = Σ(flow=OUT)`, `ingreso = Σ(flow=IN)`; los `TRANSFER_*` quedan fuera
por el propio movimiento, no por la categoría.

### 34.1 — Columna + migración con backfill (sin cambio de comportamiento)
- Migración `z3p58r0on2q1p7`: crea el enum `transactionflow`, añade la
  columna **NULLABLE**, hace **backfill** derivando `flow` de la
  interpretación actual por categoría (`is_transfer`+`kind`) e índice
  parcial `ix_transactions_user_flow_active`.
- El backfill **REPRODUCE** los datos actuales tal cual (incluidos los bugs):
  garantiza que 34.2 sea una equivalencia exacta viejo↔nuevo. La corrección
  llega al reimportar con 34.3 (el signo del extracto manda).

### 34.2 — Saldo + ahorro-neto + cashflow leen de `flow` (arregla los bugs)
- `accounts.repository` (`get_balances_for_user`,
  `get_net_savings_movement_for_account`): el signo se deriva de `flow` +
  `account.nature`. Helpers `_is_outflow` / `_is_inflow` /
  `_is_internal_transfer` con **fallback a categoría** para filas sin flow.
- `dashboard.repository`: income/expense/transfer por `flow` (helpers
  `_is_income` / `_is_expense` / `_is_internal_transfer`, NULL-safe). Se
  preservó el carve-out de la pata-activo de un par financiado y el filtro
  `currency == account.currency`.
- Golden tests (`tests/test_flow_money_model.py`) fijan la semántica nueva
  con los dos bugs medidos.

### 34.3 — El import y los forms escriben `flow`
- `transfers/service.classify_import_flow`: decide `flow` de una fila
  importada. Dirección por orden de fiabilidad: **signo del extracto**
  (invariante duro) → texto (`infer_transfer_kind`) → `category_kind` →
  `None` (sin clasificar). "Transfer-ness" de la categoría resuelta O de la
  descripción (`is_internal_movement_text`: transferencia / `ADEUDO` /
  liquidación / operación financiada; **BIZUM excluido** a propósito).
- `transactions/service`: `create_transaction` / `update_transaction` aceptan
  `flow` del cliente; si no llega, lo derivan de la categoría (puente de
  transición hasta 34.6).
- Todos los caminos de transferencia escriben `flow`: `mark_as_transfer`,
  `link_manually`, `auto_match`, `reclassify_bulk`,
  `convert_to_internal_transfer`, `convert_to_debt_operation`.

### 34.x — Mejoras de UX y consistencia incluidas en esta fase
- **Anulación del "cargo espejo"** (`convert_to_debt_operation` +
  `find_mirror_charge`): al registrar una operación financiada como deuda, el
  `ADEUDO` del mismo importe que la compensa se mueve a la papelera
  (reversible) → saldo neto 0 + deuda creada. El response devuelve
  `absorbed_mirror_amount`.
- **Saldo = caja real**: la lista de cuentas dejó de mostrar "ahorro neto"
  en la principal (carve-out de PHASE-32 que confundía: la principal salía
  igual que el cashflow del mes). Ahora todas muestran su caja real; el
  ahorro neto / tasa de ahorro siguen como métricas del dashboard. El
  agregado de patrimonio ya usaba caja → `net_worth` sin cambios.
- **`POST /accounts/{id}/reconcile`** ("Cuadrar saldo"): ancla el saldo de
  una cuenta de **activo** al valor real declarado por el usuario, ajustando
  `opening_balance = saldo_real − Σmovimientos`. Sirve para fijar el inicial
  y re-cuadrar. 400 si no es ASSET.
- **`POST /transactions/bulk-categorize`**: recategoriza una selección
  explícita (checkbox) de tx. **Relabel puro**: no toca `flow` ni el par de
  transferencia, así que el dinero no cambia.
- **Forms web**: segmento **[Gasto]/[Ingreso]** que escribe `flow` directo
  (las transferencias se gestionan en su flujo propio, no como un tercer
  botón). Tarjeta de crédito: bloque de financiación **opcional y plegado**
  (una tarjeta que pagas entera cada mes no necesita TIN/plazo).
- **`get_transaction_month_bounds`**: meses mín/máx con tx para acotar el
  navegador de período del Análisis.

## Endpoints añadidos / modificados
- `POST /accounts/{account_id}/reconcile` — cuadrar saldo (activos).
- `POST /transactions/bulk-categorize` — recategorizar selección (relabel).
- `POST/PATCH /transactions` — aceptan y devuelven `flow`.
- `POST /imports/...` — el pipeline escribe `flow` por fila.

## Migraciones
- `z3p58r0on2q1p7_transaction_flow_enum.py` — enum + columna NULLABLE +
  backfill + índice parcial. Idempotente (`WHERE flow IS NULL`).

## Archivos clave
### Backend
- `transactions/models.py` — enum `TransactionFlow` + columna `flow` + índice.
- `accounts/repository.py` — saldo/ahorro-neto desde `flow`+`nature`.
- `dashboard/repository.py` — cashflow desde `flow` (helpers NULL-safe).
- `transfers/service.py` — `classify_import_flow`,
  `is_internal_movement_text`, escritura de `flow` en todos los caminos,
  absorción del cargo espejo.
- `imports/service.py` — `_parse_row` resuelve `flow` por fila.
- `transactions/service.py` + `router.py` — flow en create/update +
  `bulk-categorize`.
- `accounts/service.py` + `router.py` — `reconcile_account_balance`.
- `tests/test_flow_money_model.py` — golden tests del modelo de dinero.

### Frontend
- `packages/types` — `TransactionFlow`, `flow` en DTOs/modelos de tx.
- `packages/services` — hooks `useReconcileAccount`,
  `useBulkCategorizeTransactions`.
- `components/transactions/transaction-form.tsx` — segmento [Gasto]/[Ingreso].
- `app/(app)/personal-finance/transactions/page.tsx` — barra de selección +
  bulk-categorize.
- `app/(app)/settings/accounts/page.tsx` + `components/accounts/account-form-fields.tsx`
  — "Cuadrar saldo" + financiación opcional en tarjeta.

## Verificación
- [x] `ruff` / `mypy app/` verdes (128 ficheros).
- [x] `pytest` backend completo — **589 verde** (incluye `test_flow_money_model`).
- [x] `pnpm lint` / `pnpm typecheck` verdes.
- [x] `pnpm test` — 71 web + 18 móvil verdes.
- [ ] Prueba manual del usuario (gate de commit):
  - El gasto del mes ya no incluye transferencias ni `ADEUDO` de tarjeta.
  - El saldo de cada cuenta cuadra con el extracto (signo del banco).
  - "Cuadrar saldo" fija el saldo real de una cuenta de activo.
  - Recategorizar en bloque no cambia el gasto/ingreso del mes.
  - Convertir una operación financiada a deuda absorbe el `ADEUDO` espejo.

## Nota de datos (auditoría 2026-06-29)
Los **dos doble-conteos** del ADR ya están corregidos en la BD real del
usuario: las filas `ADEUDO MENSUAL DE TARJETA` y `OPERACIÓN FINANCIADA CON
TARJETA` quedaron en `TRANSFER_OUT` al reimportarse con el pipeline 34.3, y
las grandes transferencias a Wise/SCL de enero ya no constan como gasto. No
hay filas con `flow` NULL. Quedan 2 movimientos pequeños tipo
"TRANSFERENCIA REALIZADA" (60 € SCL, 55 € a una persona) clasificados como
gasto; parecen pagos reales a terceros (no traspasos propios) y se dejan como
están salvo indicación del usuario.

## Limitaciones conocidas
- **Fallback a categoría** vivo (helpers `_is_*`) hasta 34.6, cuando todo el
  write path escriba `flow` y se elimine el join a `Category` de la
  matemática del dinero.
- El form web no expone "[Entre mis cuentas]" como tercer botón: las
  transferencias siguen creándose desde su flujo propio (mark / convert).

## Próxima fase
PHASE-34.6 — limpieza: quitar `category.kind`/`is_transfer` de la matemática
del dinero y reducir `/transfers` a red de seguridad.
