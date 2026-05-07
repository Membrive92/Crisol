# PHASE-17.3 — Reconciliación de imports con tx `expected`

**Estado**: ✅ completada
**Rama**: `feat/phase-17.3-fixed-expenses-reconciliation`
**Fecha de merge**: 2026-05-07

## Objetivo

Cerrar el flujo del autoposting introducido en PHASE-17.2 sin
generar duplicados. Cuando el cron de autopost crea una tx
`source=expected` el día 1 ("hipoteca, esperada") y luego el
banco trae el cargo real en el CSV el día 5, el pipeline de
imports debe detectar que ya hay una `expected` para ese cargo y
fusionarlas — la `expected` recibe el `import_hash`, no se crea
una segunda fila.

## Qué se implementó

### Backend

- **Nuevo `fixed_expenses/reconciliation.py`** con
  `reconcile_with_expected(db, user_id, *, occurred_at, amount,
  currency, description, import_hash)`:
  - Filtra candidates por `user_id + source=expected +
    import_hash IS NULL + deleted_at IS NULL + amount exacto +
    currency + occurred_at ±3 días`.
  - Refina con prefijo común normalizado entre `description` del
    import y `description` del candidate. Reusa
    `normalize_merchant` y `_common_prefix` del detector
    (PHASE-13.1 + 14.7) — mismo umbral `MIN_COMMON_PREFIX = 6`.
  - Si hay múltiples candidates, elige el más cercano en fecha
    (el banco normalmente carga con 1-2 días de retraso).
  - Si match: asigna `import_hash`, refresca `description` con la
    del banco (más legible que el `raw_description` heredado del
    fixed_expense original) y deja `source=expected` (el
    `import_hash` no nulo es el indicador de "conciliada").
  - Normaliza tz: si el caller pasa naive, asume UTC. Las txs
    en BD son TIMESTAMPTZ — ambos lados se normalizan antes de
    comparar.
- **Hook en `imports/service.py`**:
  - Antes del `db.add(Transaction(...))` para una fila no
    duplicada, llama a `reconcile_with_expected`.
  - Si devuelve match → cuenta como `reconciled`, no inserta.
  - `rows_ok = inserted + reconciled` — desde la perspectiva del
    usuario son txs nuevas en su lista (la `expected` ahora
    tiene `import_hash`).
- **Tests** (6 nuevos en `tests/test_fixed_expenses_reconciliation.py`):
  - Match cuando coinciden todos los criterios → asigna
    `import_hash`, refresca `description`, mantiene `source`.
  - No match si `amount` distinto.
  - No match si fuera de la ventana ±3 días.
  - No match si merchant sin prefijo común suficiente.
  - No match si la `expected` ya tiene `import_hash` (no doble
    reconciliación).
  - Smoke del pipeline completo: CSV con un cargo de hipoteca →
    no crea tx nueva, asigna `import_hash` a la `expected` →
    `rows_ok = 1`, no hay duplicada en BD.

Suite backend: **238/238** (+6 nuevos sobre 232).

### Frontend

Sin cambios — el `OriginBadge` de PHASE-17.2 ya distingue
visualmente las `expected` con palette warning. Las
reconciliadas siguen apareciendo como "Esperada" pero con
`import_hash` no nulo. La UI no diferencia (todavía) entre
"esperada pendiente de banco" y "esperada conciliada con
banco" — ver limitaciones.

## Archivos clave

- `backend/app/modules/personal_finance/fixed_expenses/reconciliation.py` (nuevo)
- `backend/app/modules/personal_finance/imports/service.py` (hook en `run_import`)
- `backend/tests/test_fixed_expenses_reconciliation.py` (6 tests)

## Verificación

- [x] `pytest tests/` — 238/238.
- [x] `pnpm typecheck` y `pnpm lint` verdes.
- [x] `pnpm test` — 40 web + 18 mobile sin regresiones.
- [ ] Smoke:
  - [ ] Crear gasto fijo con auto_post on (hipoteca 800€).
  - [ ] Forzar autopost → aparece tx "Esperada".
  - [ ] Importar CSV del banco con la misma carga 1-3 días después.
  - [ ] La tx "Esperada" recibe `import_hash` (visible en detalle)
        y la lista no tiene duplicada.
  - [ ] Importar otro CSV con un cargo distinto pero mismo amount
        → se crea tx nueva, no toca la conciliada.

## Decisiones tomadas

- **Tolerancia de ±3 días**. Cubre el caso normal del banco
  (cargo en weekend → carga el lunes, festivos, etc.) sin
  generar matches espurios. Si el cron del banco tarda más, el
  usuario añadirá la tx manualmente y la `expected` quedará
  pendiente — el siguiente cron de autopost no creará otra
  porque `next_due` ya avanzó.
- **Refinar con prefijo común ≥ 6 chars**. Sin esto, dos cargos
  con mismo amount en mismo rango (ej. dos suscripciones de
  9.99€) se fusionarían incorrectamente. Reusa el umbral del
  detector PHASE-14.7 — coherente con cómo se decide "esto es
  el mismo merchant".
- **Match por exact amount, no rango**. Los gastos fijos en el
  scope actual (PHASE-17.2) son sólo cantidad fija. Si en una
  fase futura abrimos el scope a variables (luz/gas), el match
  necesitaría un rango (ej. ±20%) y entonces el merchant sería
  todavía más importante para evitar falsos positivos.
- **`source` se queda `expected` tras reconciliar**. La
  alternativa "cambiar a `import` cuando se concilia" pierde
  trazabilidad: el usuario no sabría que esa tx vino del
  autopost antes que del banco. Mantener `source=expected` +
  `import_hash IS NOT NULL` deja claro: "fue auto-posteada y
  luego confirmada por el banco".
- **Refrescar `description` con la del banco**. La descripción
  del banco suele ser más informativa ("TRANSFERENCIA HIPOTECA
  SANTANDER OFICINA 1234") que el `raw_description` que vino
  del último cargo detectado.
- **`reconciled` cuenta como `rows_ok`**. Desde el flujo del
  usuario, importar 5 filas que reconcilian 3 + insertan 2 es
  "5 filas procesadas correctamente". Distinguirlas a nivel de
  job sería deseable pero requiere schema change al modelo
  `ImportJob` — fuera de scope.

## Limitaciones conocidas

- **UI no distingue conciliada vs pendiente**. Una tx
  `source=expected` con `import_hash IS NOT NULL` ya está
  confirmada por el banco; sin él, sigue pendiente. Una mejora
  futura: badge "Conciliada" tras `import_hash` no nulo. Para
  primera versión la diferencia es invisible — ambas se
  muestran como "Esperada".
- **Sin caducidad de `expected` no conciliadas**. Si pasan 30
  días y el banco nunca trajo el cargo, la `expected` se queda
  ahí. El usuario puede borrarla manualmente. Mejora futura:
  endpoint o cron que limpia las `expected` viejas
  no-conciliadas con un mensaje "este cargo no llegó del
  banco, ¿lo confirmas como manual o lo elimino?".
- **No reconcilia con tx `manual` ni `receipt`**. Si el usuario
  añadió la tx manualmente antes de que el cron de autopost la
  creara, ahora habría duplicada. Caso raro (autopost corre a
  las 4:30 AM UTC) pero posible. Mejora futura: que autopost
  primero busque tx del usuario en ±3 días con mismo
  merchant+amount y skip si encuentra.
- **`rows_reconciled` no se reporta en el job response**. El
  contador interno existe pero no se persiste. Si en el futuro
  la UI quiere distinguir "X importadas + Y reconciliadas",
  añadir `rows_reconciled` a `ImportJob`.

## Cierre PHASE-17

PHASE-17 cerrada (3 sub-fases ✅). El área de "Gastos fijos"
(antes "Subscripciones") ahora cubre el flujo completo:
detecta patrones de cualquier gasto fijo recurrente (17.1),
puede auto-postear los seguros con opt-in por fila (17.2) y
reconcilia automáticamente con los imports del banco (17.3).
