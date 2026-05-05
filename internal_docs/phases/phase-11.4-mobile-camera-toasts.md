# PHASE-11.4 — Polish del flujo de captura mobile (toasts)

**Estado**: ✅ completada
**Rama**: `feat/phase-11.4-mobile-camera`
**Fecha de merge**: 2026-05-05

## Re-encuadre del alcance

El backlog tenía como follow-up "captura de tickets por cámara
mobile" desde PHASE-5.2. Al inspeccionar el código antes de tocar
nada se encontró que **la cámara ya estaba implementada**:

- [`apps/mobile/app/(modules)/personal-finance/receipt/new.tsx`](../../apps/mobile/app/(modules)/personal-finance/receipt/new.tsx)
  ya tenía `handleTakePhoto` con
  `ImagePicker.launchCameraAsync({ mediaTypes: ImagePicker.MediaTypeOptions.Images, quality: 0.8 })`,
  permisos vía `requestCameraPermissionsAsync`, y dos botones
  ("Cámara" + "Galería") en la UI.

El backlog estaba desfasado. Lo que **sí faltaba** era cerrar el
flujo con el sistema de toasts global de PHASE-11.3 — la pantalla
seguía usando `Alert.alert` para errores no bloqueantes y un texto
inline rojo para los fallos de extracción / confirm. Es lo que
hace esta fase.

## Objetivo

Migrar todos los feedbacks transitorios del flujo de captura
mobile a `toast.show(...)` — confirmación de éxito tras añadir el
ticket, errores no bloqueantes (permisos, extracción fallida,
confirm/reject fallidos), y unify con la convención establecida
en PHASE-11.3. Mantener `Alert.alert` solo para confirms
destructivos genuinos (rechazar ticket).

## Qué se implementó

`apps/mobile/app/(modules)/personal-finance/receipt/new.tsx`:

- **`handlePickFromLibrary` / `handleTakePhoto`**: el `Alert.alert`
  de "Permiso necesario" pasa a `toast.warning(...)`. No bloquea
  el flujo y no roba el foco.
- **`handleAnalyze`**: `extractMutation` añade `onError` que
  dispara `toast.error("Error al analizar: …")` con sugerencia
  "¿Está Ollama corriendo?" cuando el mensaje no es informativo.
  El error inline `<Text style={styles.errorText}>` se eliminó —
  el toast cubre el caso.
- **`handleConfirm`**: `onSuccess` dispara
  `toast.success("Ticket añadido como transacción.")` antes del
  `router.replace` para que el usuario vea el feedback al volver
  a la lista de tickets. `onError` → `toast.error(...)` con el
  mensaje del backend.
- **`handleReject`**: `Alert.alert` se mantiene (es un confirm
  destructivo bloqueante por diseño) pero `onSuccess` →
  `toast.info("Ticket rechazado.")` y `onError` →
  `toast.error(...)`.
- **`<ReceiptCaptureForm errorMessage={...}>` deja de pasarse**.
  El error de confirm ahora vive en el toast; el prop sigue
  opcional en el form para futuras validaciones locales que
  necesiten texto inline (mantiene el contrato).
- Estilo `errorText` eliminado del `StyleSheet` — quedaba
  huérfano tras quitar el bloque inline.

Sin cambios en backend, packages shared, web, ni tests existentes.

## Flujo técnico

```
 Usuario abre /receipt/new
    ▼
 [Cámara] [Galería]
    │
    ├── Permiso denegado → toast.warning("Concede acceso a la cámara/galería…")
    └── Permiso ok → ImagePicker captura/escoge imagen → setPicked

 [Analizar]
    │
    ▼ extractMutation.mutate(file)
    ├── onSuccess → setStagedReceipt + setStagedExtraction → ReceiptCaptureForm
    └── onError → toast.error("Error al analizar: …")

 ReceiptCaptureForm: usuario edita y pulsa [Confirmar]
    │
    ▼ confirmMutation.mutate(payload)
    ├── onSuccess → toast.success("Ticket añadido como transacción.")
    │              router.replace('/(tabs)/receipts')
    └── onError → toast.error("Error al confirmar: …")

 [Rechazar]  → Alert.alert (confirm destructivo bloqueante)
    │ Cancelar / Rechazar
    ▼ rejectMutation.mutate()
    ├── onSuccess → toast.info("Ticket rechazado.")
    │              router.replace('/(tabs)/receipts')
    └── onError → toast.error("Error al rechazar: …")
```

## Archivos clave

- `apps/mobile/app/(modules)/personal-finance/receipt/new.tsx`
  (errores migrados a toasts; success toast tras confirm/reject;
  estilo huérfano eliminado)

## Endpoints

Ninguno.

## Migraciones

Ninguna.

## Verificación

- [x] `pnpm typecheck` verde.
- [x] `pnpm lint` verde.
- [x] `pnpm test` — 23/23 web sin regresiones.
- [ ] Smoke en Expo:
  - [ ] Permiso de cámara denegado → toast warning bottom.
  - [ ] Foto + Analizar → con Ollama corriendo: form de
        confirmación; sin Ollama: toast.error.
  - [ ] Confirmar → toast.success y vuelve a la lista de tickets.
  - [ ] Rechazar → Alert nativo destructivo → toast.info y vuelve.

## Decisiones tomadas

- **`Alert.alert` sólo para confirms destructivos**. Toasts son
  para feedback pasivo: éxito de mutation, error no recuperable
  por sí mismo, info de permisos. `Alert` interrumpe la UX y debe
  reservarse para acciones que necesitan respuesta del usuario
  (rechazar ticket, mover a papelera, eliminar permanente).
- **`toast.warning` para permisos denegados** en lugar de
  `toast.error`. Errores son cosas que rompieron; un permiso
  denegado es un estado del sistema que el usuario puede
  arreglar. Warning encaja mejor.
- **`toast.success` antes del `router.replace`**. El render de la
  toast queue sobrevive al cambio de ruta porque el `<Toaster />`
  vive en el root layout (PHASE-11.3). El usuario ve el feedback
  al aterrizar en la lista.
- **Mensaje de extracción incluye "¿Está Ollama corriendo?"**
  cuando el error no trae información. Es la causa #1 de fallo en
  desarrollo y reduce la fricción de diagnóstico.
- **Mantener el prop `errorMessage` opcional en
  `ReceiptCaptureForm`** aunque ahora no lo pasemos. El form sigue
  siendo reusable; un futuro flujo (web equivalente) podría
  pasar errores de validación locales que tengan más sentido
  inline que como toast.
- **Borrar el estilo `errorText` huérfano**. Regla de CLAUDE.md
  ("no half-finished"): si el bloque que lo usaba se eliminó, el
  estilo se va con él.
- **Sin tests UI mobile** (heredado de PHASE-2.2: `jest-expo`
  pendiente). Toda la lógica de toast (queue, dismiss, render)
  está cubierta por los tests web del Toaster en PHASE-11.3 —
  mismo store.

## Limitaciones conocidas

- **Smoke real con cámara/Ollama pendiente**. El cambio es de
  UX (toasts en lugar de Alert/inline) — la captura ya funcionaba.
  Verificación manual en Expo + dispositivo real requerida.
- **Sin animación específica de éxito** tras confirm. El toast
  estándar (5s, kind success, sin acción) basta. Si en el futuro
  se quiere una transición destacada (confeti, haptic feedback),
  el toast se queda como confirmación textual y se añade el
  efecto sobre la lista de tickets.
- **Imports + receipts confirm web siguen sin toasts**. Sigue en
  el backlog como follow-up trivial — basta envolver los
  `onSuccess` / `onError` de las mutations con `toast.show(...)`.

## Próxima fase

Sin definir. Cierra el ciclo de PHASE-11 (infra y polish):
APScheduler nocturno + currency store cross-platform + toasts
global + adopción del sistema en flujo de captura mobile.

Candidatos visibles del backlog:

- **Imports + receipts confirm web a toasts** (trivial, ~30 min).
- **Detección de subscripciones recurrentes** vía AI.
- **Modelo de presupuestos por categoría** con alertas.
- **Cámara mobile UI/UX polish** (haptic feedback, retake antes
  de Analizar, retry sin volver a tomar foto).
- **Test setup mobile (`jest-expo`)** para empezar a cubrir UI
  RN.
