# PHASE-39 — Saldo del extracto como ancla del saldo real

**Estado**: ✅ código completo y verde (pendiente prueba manual del usuario + commit)
**Rama**: trabajo directo en `main` (convención del proyecto)
**PR**: — (push directo)
**Fecha**: 2026-07-13

## Objetivo

Capturar la columna **Saldo** de los extractos bancarios importados
(saldo de la cuenta tras cada movimiento) y usarla como **fuente de
verdad del saldo real**: cada import ancla automáticamente el
`opening_balance` de la cuenta al saldo que declara el banco, eliminando
los descuadres estructurales del saldo derivado por pura acumulación
(cuentas arrancando en 0, movimientos ausentes, escenarios no cubiertos
por el clasificador de `flow`).

Origen: auditoría de integridad 2026-07-13 — BBVA en −11.777,93 € con
`opening_balance = 0` cuando el extracto real (captura del usuario)
decía 5.817,76 € a 30/04/2026.

## Qué se implementó

### Backend

- **Parser** (`imports/parser.py`): nuevo rol de columna
  `statement_balance` con hints propios (`saldo`, `balance`) en
  `_classify_columns`. La regla histórica se conserva intacta: "saldo"
  JAMÁS matchea el rol `amount` (el comentario IMPORTANT y su test de
  regresión siguen vigentes). Los smart parsers (XLSX y PDF) emiten la
  key nueva; los legacy la sirven vía mapping explícito del usuario.
- **Schemas**: `statement_balance` en `TARGET_FIELDS`,
  `ImportColumnMappings` e `ImportPreviewRow`; nuevo
  `ImportBalanceAnchor { balance, date }` en `ImportJobResponse`
  (poblado desde `preview_payload["balance_anchor"]`, no es columna).
- **Modelo + migración `d7t03v5sq7u6t2`** (aditiva, nullable,
  reversible):
  - `transactions.statement_balance NUMERIC(14,2) NULL` — saldo del
    extracto tras el movimiento. Informativo/auditable; NO participa en
    el cálculo del saldo ni en el `import_hash`.
  - `accounts.anchored_statement_balance NUMERIC(14,2) NULL` — saldo
    REAL declarado en el último anclaje, a fecha `opening_balance_date`.
- **Service de imports** (`imports/service.py`):
  - `_parse_balance` — parseo FIRMADO y tolerante (0 y negativos
    válidos; ilegible → `None`, nunca tumba la fila). Comparte la
    normalización de separadores con `_parse_amount_signed`
    (`_normalize_decimal_separators`, extraída).
  - `ParsedRow.statement_balance` + persistencia en `_new_tx`.
  - **Backfill en duplicados**: las filas saltadas por hash (reimport)
    rellenan `statement_balance` de la tx existente si era NULL —
    reimportar el histórico enriquece sin duplicar.
  - `_pick_balance_anchor` — elige el ancla del lote: el movimiento
    cronológicamente más reciente con saldo. Detecta la dirección del
    fichero (nuevo→viejo estilo BBVA vs viejo→nuevo) por fechas
    primera/última; con empate (extracto de un día) valida la
    aritmética de la cadena `saldo[i] ± importe` en ambas hipótesis.
- **Service de accounts** (`accounts/service.py`):
  - `anchor_account_balance_at` — variante automática de "Cuadrar
    saldo" (PHASE-34): `opening_balance = saldo(D) − Σmov(≤D)` con la
    MISMA expresión de signo del saldo mostrado
    (`get_account_movement_until`, nueva, replica `signed_amount_expr`
    con el carve-out H-02 + corte por fecha). Guardas: solo ASSET,
    divisa coincidente, y **un ancla más reciente nunca se pisa con una
    más vieja**. Best-effort: si no procede, el import sigue válido.
  - `re_anchor_from_stored` — cuando un import añade historia ANTERIOR
    al ancla (con o sin columna Saldo), la Σmov(≤ancla) cambia; este
    helper re-deriva el opening desde el ancla PERSISTIDA preservando el
    invariante `saldo(fecha_ancla) == anchored_statement_balance`. Sin
    él, reimportar extractos viejos corrompería el saldo en exactamente
    la suma de las filas nuevas.
  - `reconcile_account_balance` (manual) ahora también persiste
    `anchored_statement_balance` — mismo mecanismo de protección.

### Frontend (web)

- Tipos (`packages/types`): `ImportPreviewRow.statement_balance`,
  `ImportColumnMappings.statement_balance?`,
  `ImportJob.balance_anchor?`.
- Wizard de mapping: campo opcional "Saldo" con auto-mapeo por
  sinónimos y fallback vacío (no fuerza una columna inexistente).
- Preview: 5ª columna "Saldo".
- Commit: toast "Saldo de la cuenta anclado a X € (fecha)" cuando la
  respuesta trae `balance_anchor`; stat "Saldo anclado" en el
  ResultStep.
- Soporte: prop `hint` en `Field`/`TextInput` (texto de ayuda).
- Móvil: sin cambios (no tiene flujo de imports).

## Decisiones de diseño

1. **El saldo NO entra en el `import_hash`.** Idempotencia intacta:
   reimportar ficheros ya importados salta las filas por hash y
   BACKFILLEA el saldo — el plan del usuario ("reimportar todo") funciona
   sin duplicar nada.
2. **Anclaje con la misma matemática que el saldo mostrado** (incluido
   el carve-out H-02): garantiza `saldo_app(D) == saldo_banco(D)`
   exacto en la fecha del ancla. Las discrepancias estructurales
   anteriores al ancla se absorben en el `opening_balance` (igual que el
   "Cuadrar saldo" manual de PHASE-34).
3. **"El ancla más reciente gana"** + `re_anchor_from_stored`: importar
   en cualquier orden (nuevo→viejo o viejo→nuevo) converge al mismo
   estado. `opening_balance_date` pasa de ser puramente informativo a
   ser LA fecha del ancla.
4. **Best-effort**: el anclaje jamás rompe un import (cuenta liability,
   divisa distinta, saldo ilegible → se salta en silencio).

## Verificación

- [x] Backend: **666 tests** (pytest) + ruff + mypy verdes.
  - Parser: rol nuevo clasificado; "Saldo" sigue sin matchear amount
    (regresión protegida); PDF smart emite el saldo; `_parse_balance`
    firmado/tolerante (10 casos); `_pick_balance_anchor` por fechas y
    por cadena (mismo día).
  - Integración: anclaje viejo→nuevo y nuevo→viejo; reimport con saldo
    ancla sin insertar (skip+backfill); extracto viejo NO pisa ancla
    nueva y re-deriva el opening; import sin saldo preserva el cuadre
    manual; liability ignorada.
- [x] Web: typecheck + lint + **95 tests**; types/services verdes.
- [x] Migración aplicada a la BD de dev; backend reiniciado y sano.
- [ ] Prueba manual del usuario: reimportar extractos BBVA con columna
      Saldo y verificar saldo final + toast de anclaje.

## Limitaciones conocidas

- El fallback de **visión** (PDF escaneado) no extrae saldo (el schema
  del modelo no lo devuelve). Follow-up si se necesita.
- Tx manuales del MISMO día del ancla que no estén en el extracto se
  incluyen en la Σ y desvían el anclaje en su importe (caso raro;
  re-cuadrable).
- Editar/borrar a mano transacciones anteriores al ancla desvía el
  saldo hasta el siguiente import o cuadre manual (mismo
  comportamiento que el "Cuadrar saldo" de PHASE-34).
- La detección de huecos (saltos en la cadena saldo±importe → "faltan
  movimientos entre X e Y") queda como follow-up natural — el dato por
  transacción ya se persiste.

## Próxima fase

Follow-ups de la auditoría 2026-07-13 (duplicados de marzo, Western
Union #4b, opening de Wise) — el reimport masivo con esta feature
resuelve el grueso del #6.
