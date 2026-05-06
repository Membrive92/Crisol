# PHASE-15.1 — Dedup de toasts repetidos

**Estado**: ✅ completada
**Rama**: `feat/phase-15.1-toast-dedup`
**Fecha de merge**: 2026-05-06

## Objetivo

Tras PHASE-14.5, crear varias transacciones consecutivas en la
misma categoría disparaba un toast por cada una — ruido visible.
Esta fase añade `dedupKey` opcional al store de toasts: dos toasts
con la misma llave se reemplazan en el sitio en lugar de apilarse.

## Qué se implementó

### Tipos shared

`packages/types/src/models/toast.ts`:
- `Toast.dedupKey?: string` — llave de deduplicación.
- `ToastInput.dedupKey?: string` — el caller la pasa al `show(...)`.

### Store

`packages/store/src/toast.ts` — `show(input)`:
- Sin `dedupKey` → comportamiento previo (apila).
- Con `dedupKey` → busca en queue un toast con misma llave; si
  existe, lo **reemplaza en su mismo índice** (no salta al final).
  Si no, apila normal. El `dismissAfterMs` se resetea con el nuevo
  toast → "renueva" el contador.

### Caller

`packages/services/src/query/hooks/useTransactions.ts` —
`useCreateTransaction.onSuccess` con alert:
- Pasa de `toast.error/warning(label)` a `toast.show({ kind, message,
  dedupKey: 'budget:${budget_id}' })`. Múltiples txs sobre el
  mismo budget muestran un único toast actualizado (no spam).

### Tests

`apps/web/components/ui/toaster.test.tsx` — 2 tests nuevos:
- `dedupKey` reemplaza en su sitio sin acumular.
- Sin `dedupKey` el comportamiento previo (apilar) se mantiene.

Suite web: **40/40** (+2 nuevos sobre 38 previos).

## Archivos clave

- `packages/types/src/models/toast.ts` (`dedupKey?` en Toast/ToastInput)
- `packages/store/src/toast.ts` (lógica de reemplazo en `show`)
- `packages/services/src/query/hooks/useTransactions.ts`
  (alert usa `dedupKey: budget:${id}`)
- `apps/web/components/ui/toaster.test.tsx` (+2 tests)

## Verificación

- [x] `pnpm typecheck` verde.
- [x] `pnpm lint` verde.
- [x] `pnpm test` — 40 web + 18 mobile.
- [ ] Smoke: crear budget categoría EUR 100. Crear 3 txs de 30€
      cada una en la misma categoría. Esperar: tras la 1ª y 2ª, no
      toast (90% no llega a 80% el primer hit, sí lo llega tras la
      segunda). Tras la 3ª (90 + 30 = 120%) → toast `over`.
      Crear otra de 5€ → mismo toast actualizado a 125%, no segundo
      apilado.

## Decisiones tomadas

- **Reemplazar en su mismo índice, no mover al final**. Mantiene
  estable la posición visual del toast — el usuario que ya estaba
  leyendo el texto no ve el toast saltar de sitio.
- **`dismissAfterMs` se renueva** con el reemplazo. Es lo que el
  usuario espera: "el toast vuelve a contar 6s desde ahora".
- **Sin `dedupKey` por defecto en los helpers procedurales**
  (`toast.success(...)`, `toast.error(...)`). El caller que quiere
  dedup pasa por `toast.show({ ..., dedupKey })`. Los helpers son
  para el caso simple.
- **Llave libre, no enum**. Que el caller decida la semántica:
  `budget:UUID`, `import:job-id`, etc. Más flexible que un set
  cerrado.

## Limitaciones conocidas

- **Sin merging de mensajes**. Si dos toasts tienen mismo
  `dedupKey` pero mensajes "diferentes-pero-relacionados"
  (improbable hoy), gana el último. Si emerge necesidad de
  agregar (ej. "X errores de import"), añadir `mergeMessage`
  callback.
- **Sin tests UI mobile** del nuevo path. La lógica de dedup vive
  en el store cross-platform; los tests web del store cubren la
  semántica.

## Próxima fase

PHASE-15.2 — Pause / cancel para subscripciones.
