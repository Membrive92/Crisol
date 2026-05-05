# PHASE-11.5 — Imports + receipts confirm web a toasts

**Estado**: ✅ completada
**Rama**: `feat/phase-11.5-web-imports-receipts-toasts`
**Fecha de merge**: 2026-05-05

## Objetivo

PHASE-11.3 introdujo el sistema global de toasts y PHASE-11.4 lo
adoptó en el flujo de captura mobile. En web quedaban tres páginas
con feedback ad-hoc inline o silencioso:

- `/personal-finance/imports/new` (3-step wizard).
- `/personal-finance/receipts/new` (subir imagen + extraer + confirmar).
- `/personal-finance/receipts/[id]` (detalle pendiente para confirmar).

Esta fase completa la adopción: éxito de mutation con
`toast.success`/`toast.info`, errores no recuperables con
`toast.error`, y dejamos inline solamente las validaciones locales
que son contexto del input (formato/tamaño de fichero).

## Qué se implementó

### `imports/new/page.tsx`

- `useCreateImport` mutation gana `onSuccess` →
  `toast.success("Importación completada: N filas añadidas.")` además
  de la transición a la step "Resultado" (que sigue mostrando el
  desglose ok/skipped/failed inline). El toast complementa al usuario
  que ya ha pasado de pantalla.
- `onError` → `toast.error("Error al importar: …")`. El error
  inline en `MappingStep` se mantiene (contexto del form donde el
  usuario puede corregir el mapping); el toast lo refuerza por si
  pierde el foco.

### `receipts/new/page.tsx`

- `useExtractReceipt` `onError` → `toast.error` con sugerencia
  "¿Está Ollama corriendo?" cuando el mensaje no aporta detalle
  (causa #1 en dev).
- `useConfirmReceipt` `onSuccess` → `toast.success("Ticket añadido
  como transacción.")` antes de `router.push`; `onError` →
  `toast.error("Error al confirmar: …")`.
- `useRejectReceipt` `onSuccess` → `toast.info("Ticket rechazado.")`;
  `onError` → `toast.error("Error al rechazar: …")`.
- **Borrado**: el `<div>` rojo inline de `extractMutation.isError`
  con `formatApiError(...)`. El toast lo cubre.
- **Borrado**: el prop `errorMessage={confirmMutation.isError ?
  ... : null}` pasado a `ReceiptConfirmForm`. Mismo patrón que
  PHASE-11.4 mobile — el prop sigue opcional en el form para
  futuras validaciones locales.
- **Mantenido inline**: el `uploadError` (validación local del
  fichero — formato no soportado, tamaño > 8 MB). Es contexto
  inmediato del input, donde el usuario corrige.
- Import `formatApiError` eliminado (ya no se usa).

### `receipts/[id]/page.tsx`

Mismo patrón que el flujo nuevo:

- `useConfirmReceipt` y `useRejectReceipt` ganan `onSuccess` y
  `onError` con toasts.
- Prop `errorMessage` eliminado del `ReceiptConfirmForm`.

## Archivos clave

- `apps/web/app/(app)/personal-finance/imports/new/page.tsx`
  (success/error toasts en `handleMappingSubmit`)
- `apps/web/app/(app)/personal-finance/receipts/new/page.tsx`
  (extract/confirm/reject a toasts; inline `extractMutation` borrado;
  `errorMessage` prop dropped del caller)
- `apps/web/app/(app)/personal-finance/receipts/[id]/page.tsx`
  (confirm/reject a toasts; `errorMessage` prop dropped)

## Endpoints

Ninguno.

## Migraciones

Ninguna.

## Verificación

- [x] `pnpm typecheck` verde.
- [x] `pnpm lint` verde.
- [x] `pnpm test` — 23/23 web (sin regresiones).
- [ ] Smoke manual:
  - [ ] Imports: subir CSV correcto → step Resultado +
        `toast.success`. Subir CSV con mapping inválido →
        `toast.error` + error inline en MappingStep.
  - [ ] Receipts new: subir imagen + Analizar sin Ollama →
        `toast.error` con hint. Con Ollama → form de confirmación.
        Confirmar → `toast.success` y volver a la lista.
        Rechazar → `toast.info`.
  - [ ] Receipts [id]: detalle pendiente → confirmar/rechazar
        emiten los mismos toasts.

## Decisiones tomadas

- **Mantener inline en MappingStep AND toast para imports**. La
  doble notificación es defensiva: el usuario que está editando el
  mapping ve el error donde puede corregirlo (`MappingStep`
  errorMessage) y el toast lo refuerza para casos en que el form
  está bajo el fold de la pantalla.
- **Borrar el inline en receipts new (extracción) AND el
  `errorMessage` del form**. A diferencia de imports, aquí el
  usuario no edita nada al recibir el error de extracción — sólo
  re-intenta o cambia de imagen. El toast cubre el caso sin
  duplicar pixeles ocupados.
- **Mantener `uploadError` inline para validación de fichero**.
  Formato no soportado o > 8 MB es validación local que el usuario
  arregla en el input; toast aquí sería ruido.
- **`toast.success("Importación completada: N filas añadidas.")`
  usa sólo `rows_ok`**. La step Resultado tiene el desglose
  completo (ok / skipped / failed). Repetir todo en el toast lo
  haría enorme. El número que importa para "¿salió bien?" es ok.
- **Sin tests nuevos**. La lógica del Toaster y del store ya está
  cubierta en PHASE-11.3 (7 tests). Estos cambios son adopción
  consistente del mismo sistema; testear los callsites no aporta
  más confianza que el smoke manual.

## Limitaciones conocidas

- **Sin tests específicos de las páginas** — la cobertura
  end-to-end de los flujos imports/receipts confirm sigue en
  smoke manual (igual que pre-PHASE-11.5). Si en una fase futura
  se añade `playwright` o equivalente, estos flujos son buen
  candidato.
- **Sin animación / haptic en éxito**. El toast estándar (5s,
  kind success) basta. Para celebrar más fuerte (confeti tras
  primer import del usuario, p.ej.) sería un follow-up.

## Próxima fase

PHASE-11.6 — Test setup mobile (`jest-expo`). Heredado del
backlog desde PHASE-2.2; las cuatro fases mobile recientes
(análisis, transactions, trash, capture) carecen de tests UI. La
infra de test mobile habilita cubrir el snackbar, el form de
captura y futuras pantallas.
