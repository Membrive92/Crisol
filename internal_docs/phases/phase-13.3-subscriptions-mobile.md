# PHASE-13.3 — Frontend mobile de subscripciones

**Estado**: ✅ completada
**Rama**: `feat/phase-13.3-subscriptions-mobile`
**Fecha de merge**: 2026-05-05

## Objetivo

Cerrar PHASE-13: pantalla mobile equivalente al web (PHASE-13.2)
reutilizando los hooks shared. Acceso desde el header de la
pestaña Análisis (junto al botón Presupuestos).

## Qué se implementó

### Componente `SubscriptionCard` mobile

`apps/mobile/components/subscriptions/subscription-card.tsx`:

- Mirror RN del web. Header con `raw_description` + amount,
  metadata (cadencia legible / categoría / confianza %), divider,
  footer con `next_due` + occurrence_count + acciones.
- `primaryAction` y `secondaryAction` props con `{ label, onPress,
  busy?, danger? }` — mismo contrato que web. Permite reusar el
  componente en pending (Confirmar + Descartar) y confirmed
  (Eliminar danger).

### Pantalla `/personal-finance/subscriptions`

`apps/mobile/app/(modules)/personal-finance/subscriptions.tsx`
(nuevo, fuera de `(tabs)/` — vista secundaria, mismo patrón que
`/budgets` y `/trash`):

- `<Stack.Screen options={{ title: 'Subscripciones' }} />`.
- Intro + botón Re-escanear (toast con `created`/`updated`).
- Sección Sugeridas (pendientes) con cards Confirmar + Descartar
  o empty state.
- Sección Confirmadas (sólo si hay) con cards Eliminar + Alert
  destructivo.
- Toasts cubren success/error vía `formatApiError` + PHASE-11.3.

### Entry point

`apps/mobile/app/(modules)/personal-finance/(tabs)/analysis.tsx`
añade un segundo Link en `headerActions`:
`Presupuestos | Subscripciones | Salir`. Mismo styling
`headerButton` introducido en PHASE-12.3.

## Archivos clave

- `apps/mobile/components/subscriptions/subscription-card.tsx` (nuevo)
- `apps/mobile/app/(modules)/personal-finance/subscriptions.tsx` (nuevo)
- `apps/mobile/app/(modules)/personal-finance/(tabs)/analysis.tsx`
  (link Subscripciones en header)

## Verificación

- [x] `pnpm typecheck` verde.
- [x] `pnpm lint` verde.
- [x] `pnpm test` — 5 mobile + 32 web sin regresiones.
- [ ] Smoke en Expo:
  - [ ] Análisis → "Subscripciones" → empty state al inicio.
  - [ ] Insertar 4 cargos mensuales mismos en Transacciones →
        volver, "Re-escanear" → toast `1 nueva` + card aparece en
        Sugeridas.
  - [ ] Tap Confirmar → toast.success + pasa a Confirmadas.
  - [ ] Tap Eliminar en una confirmada → Alert destructivo →
        confirm → toast + desaparece.

## Decisiones tomadas

- **Pantalla fuera de `(tabs)/`**. Misma decisión que budgets y
  trash — vista secundaria, no merece slot principal.
- **Re-escanear como botón outline** (no FAB). Es acción
  ocasional (el cron diario hace lo normal); botón outline en
  línea con la intro lo hace descubrible sin ser invasivo.
- **Alert destructivo sólo para Eliminar confirmada**. Confirm
  porque borra una decisión del usuario; los flujos pending →
  confirmed/dismissed no necesitan confirm (son reversibles
  ejecutando la acción opuesta).
- **No repito el componente "categoría editable" mobile** (web
  tampoco lo expone — backend no permite editar `category_id` de
  una subscripción). Decisión heredada de PHASE-13.1.
- **Sin tests UI mobile** para esta fase. Mismo razonamiento que
  PHASE-12.3: la prioridad fue cerrar la feature visible; la
  cobertura UI mobile es follow-up del backlog (heredado desde
  PHASE-2.2 / parcialmente atajado en PHASE-11.6).

## Limitaciones conocidas

- **Sin tests UI mobile** (heredado).
- **Sin sección "Descartadas"** (heredado de web — backend ya lo
  expone vía `?status=dismissed`).
- **Sin pull-to-refresh** en la pantalla. Fácil de añadir si se
  prioriza.

## Cierre de PHASE-13

PHASE-13 entera (backend + web + mobile) cerrada. Sistema
heurístico sin IA detecta subscripciones recurrentes. Cron
nocturno + endpoint manual. Web y mobile permiten confirm /
dismiss / delete con propagación correcta de status entre vistas.

Backlog ahora apunta a follow-ups menores:

- Edición inline de amount en presupuestos (web + mobile).
- Notificaciones proactivas de budget over.
- Sección "Descartadas" en subscriptions UI (datos ya en backend).
- Detector con IA (Ollama) si los falsos positivos / negativos
  reales molestan.
- Cobertura UI mobile (analysis, transactions, trash, capture,
  budgets, subscriptions).
