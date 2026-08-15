# PHASE-48 — Liquidación anticipada: concepto, doble saldo y reparación de julio

**Estado**: 📋 planificada — v2, sustituye íntegramente a la versión anterior
de este fichero (escrita antes de PHASE-47; numeración y prerequisitos
actualizados a la realidad post-47).
**Jerarquía**: este doc manda sobre la v1 en todo. Convenciones de
implementación: las del plan de 47 (FK a `users`, UUID en Python, tests
verificados rompiendo el código, `down_revision` de `alembic heads`, golden
byte a byte).
**Depende de**: 47.A (dominio consolidado en `debt/`) y **47.B cerrado**
(bandeja + detalle `/debt/{account_id}` + parada 2 hecha). **Independiente
de 47.C** — puede ejecutarse durante el mes de observación de 47.B, lo que
adelanta la reparación de julio.
**Caso confirmado por el usuario (2026-08-12)**: los 4 ADEUDO de julio
(406,33 · 384,38 · 164,94 · 143,99) son **liquidaciones anticipadas de
compras aplazadas de la tarjeta**. Son la regresión de esta fase y los
primeros settlements reales.

---

## 0. Qué resuelve

1. El modelo no puede representar una liquidación anticipada: solo existe
   "pago de cuota" (`paid_at`). El cargo de liquidación = **principal
   pendiente** (± devengado ± comisión), nunca Σ de cuotas restantes —
   la diferencia son los **intereses condonados**, que hoy no tienen dónde
   vivir y acabaron en `assumed_unregistered_debt` (el lío original).
2. **Las dos verdades del MUX** (pregunta abierta del HANDOFF y del §9 del
   plan de 47) se responden aquí: no se reducen a una — se nombran y cada
   consumidor usa la suya (§48.1, doble saldo).
3. El patrimonio neto está **infravalorado**: resta intereses futuros no
   devengados. Se corrige (con golden).

## 48.1 — Modelo: estado de cuota, entidad de liquidación y doble saldo

### Migraciones (aditivas; DDL conceptual — ajustar a convención Alembic del repo)

```sql
-- 1: estado de cuota
CREATE TYPE installment_status AS ENUM
  ('PENDING','PAID','ASSUMED_PRE_WINDOW','CANCELLED_EARLY');
ALTER TABLE liability_installments
  ADD COLUMN status installment_status NOT NULL DEFAULT 'PENDING',
  ADD COLUMN settlement_id UUID NULL;
-- Backfill (en la migración: es reproducción de estado, no corrección):
--   paid_at IS NOT NULL AND paid_transaction_id IS NOT NULL → 'PAID'
--   paid_at IS NOT NULL AND paid_transaction_id IS NULL     → 'ASSUMED_PRE_WINDOW'
--   paid_at IS NULL                                          → 'PENDING'
-- paid_at NO se elimina: sigue siendo la fecha del hecho.

-- 2: la liquidación
CREATE TABLE debt_settlements (
  id UUID PRIMARY KEY,                       -- uuid4 en Python (convención)
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  transaction_id UUID NOT NULL REFERENCES transactions(id),
  settlement_date DATE NOT NULL,
  kind VARCHAR(8) NOT NULL,                  -- 'TOTAL' | 'PARTIAL'
  principal_settled NUMERIC(14,2) NOT NULL,
  accrued_interest NUMERIC(14,2) NOT NULL DEFAULT 0,
  fee NUMERIC(14,2) NOT NULL DEFAULT 0,
  residual NUMERIC(14,2) NOT NULL DEFAULT 0,
  residual_note TEXT,
  interest_saved NUMERIC(14,2) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);
```

`liability_installments.settlement_id` → FK lógica a `debt_settlements`
(nullable; solo cuotas `CANCELLED_EARLY`).

### Reversión — acción propia, NO el undo de bandeja

Borrar un settlement: sus cuotas `CANCELLED_EARLY → PENDING`
(`settlement_id = NULL`), transacción des-enlazada. Vive como acción
explícita en el detalle de la deuda ("Revertir liquidación", con
confirmación). **El undo de la bandeja de 47 no la cubre** — límite del
anexo 47 §B: el undo de bandeja es solo para acciones tipo-vínculo; esto
es tipo-asistente y usa su reversión propia.

### Doble saldo (la respuesta a las dos verdades)

| Saldo | Definición | Consumidor |
|---|---|---|
| `outstanding_principal` | Σ `principal` de cuotas `PENDING` | **Deuda económica**: patrimonio neto, dashboard-summary, cabecera del detalle, veredicto |
| `pending_total` | Σ `payment` de cuotas `PENDING` | Informativo: "total si sigues el plan" (etiquetado así en UI) |

Golden obligatorio: el patrimonio **cambia** con esta fase (sube — deja de
restar intereses no devengados) y cada delta debe ser explicable por
plan. El MUX de PHASE-36 (`resolve_liability_outstanding`) pasa a devolver
ambos con nombre; ningún consumidor recibe "el saldo" sin apellido.

## 48.2 — Motor de recomputación (una pieza, tres usos)

`debt/recompute.py` — **puro** (sin BD/red/reloj; test de pureza por AST,
mismo patrón que `classification.py`):

```python
def recompute_schedule(
    plan: ScheduleInput,                  # cuotas vivas + TIN + fechas
    change: NewPrincipal | NewRate,       # amortización parcial | revisión de tipo
    mode: Literal["CUOTA", "PLAZO"],      # qué se mantiene constante
) -> ScheduleResult:                      # cuadro nuevo + interest_delta
```

- **Uso 1 (esta fase)**: liquidación parcial → `NewPrincipal`.
- **Uso 2 (esta fase)**: **simulador what-if** = el mismo motor sin
  persistir (`dry_run` es no-escribir, no un flag del motor: el motor es
  puro siempre). Endpoint `POST /debt/{account_id}/simulate` → cuadro
  resultante + `interest_saved` + nueva cuota o nueva fecha fin + la línea
  informativa "amortizar rinde {TAE}% garantizado" (dato, no consejo).
- **Uso 3 (futuro, no implementar)**: hipoteca variable — una revisión de
  tipo es `NewRate` + regenerar restante. La firma se generaliza HOY
  (coste ~0) para que esa nota de backlog sea enchufar, no rediseñar.
- Test central: `dry_run ≡ real` — simular y ejecutar producen números
  idénticos.

## 48.3 — Flujo de liquidación TOTAL

**Entradas** (dos): item `POSSIBLE_SETTLEMENT` de la bandeja → `accept`
lanza este asistente (tipo-asistente: el item muestra "Gestionar →", no
"Deshacer"); y botón "Liquidar anticipadamente" en el detalle
`/debt/{account_id}`.

1. Selección: transacción del cargo + plan(es).
2. **Esperado** = `outstanding_principal`(fecha) + devengado pro-rata del
   periodo (default **0** — los aplazados de tarjeta rara vez lo cobran;
   editable) + comisión (editable).
3. Cuadre con `DEBT_SETTLEMENT_TOLERANCE_EUR` (0,50):
   - **Dentro** → cuotas restantes → `CANCELLED_EARLY` + `settlement_id`
     (NUNCA `PAID`: se condonaron — los intereses realmente pagados quedan
     veraces), settlement creado con `interest_saved` = Σ `interest` de
     las canceladas, plan cerrado.
   - **Fuera** → desglose asistido: componentes editables + `residual` con
     nota obligatoria. Nada se fuerza en silencio.
4. **Cargo que liquida varios planes**: reparto propuesto proporcional a
   los principales pendientes; el usuario confirma o ajusta; un settlement
   por plan, misma `transaction_id`.
5. **Momento-recompensa**: "Plan liquidado — te has ahorrado
   {interest_saved} € de intereses". El acto financieramente correcto se
   celebra con el dato, no se castiga con un descuadre.

## 48.4 — Liquidación PARCIAL

Mismo flujo con importe < principal pendiente → el asistente pregunta
**cuota o plazo** → `recompute_schedule` → cuadro regenerado (las cuotas
viejas `PENDING` se sustituyen; las `PAID` históricas intactas) +
settlement `PARTIAL` con su `interest_saved` (Δ intereses entre cuadros).

## 48.5 — Reparación de julio (los 4 cargos reales)

1. **Deshacer el estado actual de los 4 cargos, cualquiera que sea su
   forma** (adopciones de la PHASE-45 del repo, cuotas marcadas, exceso en
   `assumed_unregistered_debt`) — con las reversiones existentes; si
   alguna forma no tiene reversión limpia, PARADA y documentar antes de
   tocar datos.
2. Vaciar el `assumed_unregistered_debt` generado por ellos.
3. Reclasificar cada cargo con el flujo 48.3 (reparto si algún cargo cubre
   más de un plan).
4. **Verificación del usuario (indelegable)**: 4 planes a saldo 0, cuotas
   recurrentes sin fantasmas, patrimonio corregido, y cada
   `interest_saved` creíble contra el documento del banco.

**Parada de datos (heredera de la parada 2)**: para los asserts finos de la
fixture `july_settlements` faltan los detalles de los 4 planes (importe
financiado, nº cuotas, cuota, pendiente al liquidar — app BBVA sección
financiaciones o PDFs de cancelación). **Fallback degradado si ya no
existen**: la fixture afirma solo (a) los 4 cargos → items
`POSSIBLE_SETTLEMENT` (guard k=1,8 de 47) y (b) la reclasificación manual
completa deja saldo 0 — sin el assert `cargo ≈ principal` exacto. Menos,
pero honesto.

## Config

`DEBT_SETTLEMENT_TOLERANCE_EUR = 0.50` (nueva). El guard k=1,8 es
`DEBT_SETTLEMENT_GUARD_K` y **ya vive en 47** — no se redefine.

## Tests

| Caso | Afirma |
|---|---|
| Regresión julio | 4 items `POSSIBLE_SETTLEMENT` → 4 settlements → saldos 0 (asserts finos según parada de datos) |
| Liquidación exacta / con comisión / fuera de tolerancia | Cierre limpio · desglose · residual con nota obligatoria |
| Multi-plan | Reparto proporcional + N settlements, una tx |
| `CANCELLED_EARLY` | NO suma a intereses pagados; `interest_saved` = Σ interest canceladas |
| Reversión | Borrar settlement → `PENDING` + saldos restaurados; el undo de bandeja NO la ofrece |
| **Doble saldo** | Golden patrimonio (sube, explicable); dashboard-summary y detalle usan `outstanding_principal`; `pending_total` etiquetado |
| Motor | Pureza AST · `dry_run ≡ real` · parcial CUOTA vs PLAZO goldens · `NewRate` compila y recomputa (sin UI) |
| Backfill migración | Los tres mapeos de estado; `downgrade` limpio |

Todos verificados **rompiendo el código** (práctica de fase heredada de 47).

## Puntos de parada

(a) Detalles de los 4 planes no recuperables → fixture degradada, avisar.
(b) Alguna forma de vínculo de julio sin reversión limpia → parar antes de
tocar datos. (c) El devengado pro-rata aparece en algún cargo real
(esperado ≠ principal por más que la comisión) → confirmar fórmula con el
documento del banco antes de codificarla.

## Fuera de alcance

Recomendación invertir-vs-amortizar (solo el dato TAE) · refinanciación/
subrogación · revisión de tipo variable en UI (solo la firma del motor —
nota de backlog "hipoteca futura") · ranking de deudas por coste (fase
corta posterior) · tocar el guard o la cascada de 47.
