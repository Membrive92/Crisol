# PHASE-15.2 — Pause / cancel para subscripciones

**Estado**: ✅ completada
**Rama**: `feat/phase-15.2-subscriptions-pause-cancel`
**Fecha de merge**: 2026-05-06

## Objetivo

Heredado del backlog: el usuario que cancela una subscripción real
(Netflix, gym) o la pausa temporalmente no tenía estado adecuado.
`dismissed` significa "el detector se equivocó" y `confirmed` es
"activa". Faltaba semántica para "sí era subscripción, ya no la
tengo" y "temporalmente suspendida".

## Qué se implementó

### Backend

- **Migración `b32c8a4d5f17`**: añade `paused` y `cancelled` al
  enum `subscriptionstatus`. Usa `ALTER TYPE ... ADD VALUE IF NOT
  EXISTS` (Postgres native, idempotente). Downgrade no-op
  documentado (Postgres no soporta DROP VALUE; revertir requeriría
  recrear el tipo y migrar rows).
- **Modelo**: `SubscriptionStatus` enum extendido con `PAUSED` y
  `CANCELLED`. Docstring renovado con la semántica de cada estado.
- **Service**: tres nuevas transiciones con guard de estado:
  - `pause_subscription`: sólo desde `confirmed` → `paused`. 409
    desde otros estados (pausar una `pending` no tiene sentido —
    primero confirma).
  - `resume_subscription`: sólo desde `paused` → `confirmed`. 409
    desde otros estados.
  - `cancel_subscription`: aceptable desde
    pending/confirmed/paused → `cancelled`. 409 sólo desde
    `dismissed` (ya está fuera del flujo).
- **Router**: tres endpoints `POST /{id}/pause`, `/resume`,
  `/cancel`.
- **Re-detection**: el `paused` y `cancelled` bloquean re-suggestion
  por la misma vía que `dismissed` — `find_by_fingerprint` matchea
  por huella sin importar status, y el service no toca `status` al
  refrescar. Sin cambios necesarios.

### Frontend (capa shared)

- `SubscriptionStatus` en `@finanzas/types` extendido a
  `'pending' | 'confirmed' | 'paused' | 'cancelled' | 'dismissed'`.
- `subscriptionsApi.pause/resume/cancel` añadidos.
- Hooks: `usePauseSubscription`, `useResumeSubscription`,
  `useCancelSubscription`. Cada uno invalida `subscriptions.all`.

### Web (`/personal-finance/subscriptions`)

- `confirmedQuery` mantiene su sección, ahora con botones
  `[Pausar]` (primary) y `[Cancelar]` (secondary danger, con
  confirm).
- Nueva sección **Pausadas** (cuando hay) con `[Reanudar]` y
  `[Cancelar]`.
- Nueva sección colapsable **Canceladas (N)** (oculta por defecto)
  con sólo `[Eliminar]`.
- Sección colapsable **Descartadas** sin cambios.

### Mobile (`/personal-finance/subscriptions`)

Espejo del web — secciones Pausadas y Canceladas, mismas
acciones. `Alert.alert` destructivo en cancel mantiene el patrón
mobile.

### Tests

`backend/tests/test_subscriptions_pause_cancel.py` (5 tests):

- `pause` sólo desde `confirmed` (409 desde pending).
- `resume` sólo desde `paused`.
- `cancel` aceptable desde pending/confirmed/paused.
- `cancel` bloqueado desde dismissed (409).
- `paused` bloquea re-suggestion: scan refresca sin tocar status.

Suite backend: **224/224** (+5 nuevos).
Frontend sin nuevos tests (UI cambios visuales sólo, hooks ya
cubiertos por convención del patrón existente).

## Archivos clave

- `backend/alembic/versions/b32c8a4d5f17_subscriptions_paused_cancelled.py` (nuevo)
- `backend/app/modules/personal_finance/subscriptions/models.py`
- `backend/app/modules/personal_finance/subscriptions/service.py` (3 funciones nuevas)
- `backend/app/modules/personal_finance/subscriptions/router.py` (3 endpoints)
- `backend/tests/test_subscriptions_pause_cancel.py` (5 tests)
- `packages/types/src/models/subscription.ts` (status extendido)
- `packages/services/src/api/endpoints/subscriptions.ts`
- `packages/services/src/query/hooks/useSubscriptions.ts` (3 hooks)
- `packages/services/src/index.ts`
- `apps/web/app/(app)/personal-finance/subscriptions/page.tsx`
- `apps/mobile/app/(modules)/personal-finance/subscriptions.tsx`

## Verificación

- [x] `pytest tests/` — 224/224.
- [x] `pnpm typecheck` y `pnpm lint` verdes.
- [x] `pnpm test` — 40 web + 18 mobile sin regresiones.
- [ ] Smoke:
  - [ ] Confirmar una pending → tap [Pausar] → pasa a Pausadas →
        tap [Reanudar] → vuelve a Confirmadas.
  - [ ] Tap [Cancelar] desde confirmada → confirm → pasa a
        Canceladas (sección colapsada).
  - [ ] Re-escanear no recrea las paused/cancelled como pending.

## Decisiones tomadas

- **Estados estrictos en transiciones**. Pause sólo desde
  confirmed (no desde pending — pausar algo sin confirmar es
  ambiguo). Resume sólo desde paused. Cancel acepta los 3 estados
  activos pero bloquea desde dismissed (ya está fuera del flujo —
  cancelarlo no añade información).
- **`paused` ≠ `cancelled` semánticamente**. Pausar = "vuelvo
  pronto, no la borres del histórico"; cancelar = "ya no la tengo,
  cierro capítulo". UX-wise el primero ofrece [Reanudar], el
  segundo no. Si fueran el mismo estado, la UI no podría
  diferenciarlos.
- **`paused` y `cancelled` bloquean re-suggestion** (mismo
  comportamiento que dismissed). `find_by_fingerprint` matchea por
  huella, no por status — si en un re-scan futuro el patrón sigue
  cumpliéndose, sólo refresca occurrence_count. El usuario no ve
  spam.
- **Migración Postgres con `ADD VALUE IF NOT EXISTS`**. Idempotente,
  no requiere transacción especial. Downgrade no-op porque PG no
  soporta DROP VALUE — documentado.
- **Sección "Canceladas" colapsable como "Descartadas"**. Patrón
  visual coherente: estados terminales fuera de flujo principal,
  ocultos por defecto, con counter "(N)" para que el usuario sepa
  que existen.
- **`primaryAction: Pausar` en confirmadas**. Pause es la acción
  esperada en el día a día (suspendí Netflix temporalmente);
  cancel queda como secondary danger. Pre-PHASE-15.2 confirmadas
  tenían sólo [Eliminar]; el usuario que quería pausar tenía que
  borrar y esperar al re-scan. Mejora de UX clara.

## Limitaciones conocidas

- **Sin tests UI** del nuevo flujo en web/mobile. Los componentes
  visuales (`SubscriptionCard`) ya están cubiertos en PHASE-13.2 y
  14.6; los nuevos handlers son mismo patrón mutation+toast que
  los previos. Smoke en runtime los verifica.
- **Sin programación de fechas para pause** (ej. "pausar hasta
  X"). Pause es indefinido — el usuario reanuda manualmente
  cuando quiera. Si emerge la necesidad, añadir `paused_until` y
  cron que reanuda al llegar la fecha.
- **Sin email/notificación** al usuario "tu subscripción
  cancelada cumplió X meses, ¿quieres limpiarla?". Sigue pendiente
  el sistema de notificaciones (deferred del backlog).

## Cierre PHASE-15

PHASE-15 cerrada (2 sub-fases ✅). Restantes deferred del
backlog conservan el motivo:
- Ollama detector — necesita dataset.
- E2E mobile (detox/maestro) — setup grande.
- Push/email — multi-platform infra + privacy review.
- Cross-currency budgets — decisión de diseño primero.
