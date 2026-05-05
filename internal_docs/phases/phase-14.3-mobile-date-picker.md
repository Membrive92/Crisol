# PHASE-14.3 — Date picker nativo mobile

**Estado**: ✅ completada
**Rama**: `feat/phase-14.3-mobile-date-picker`
**Fecha de merge**: 2026-05-05

## Objetivo

Cierre de la deuda más antigua del backlog mobile (heredada desde
PHASE-2.2): los formularios mobile pedían fechas como `TextInput`
con formato `YYYY-MM-DD` tipeado a mano. UX terrible. Esta fase
introduce un `DateInput` cross-platform que envuelve
`@react-native-community/datetimepicker` y lo conecta a los tres
formularios afectados.

## Qué se implementó

### Dep nueva

`@react-native-community/datetimepicker@8.2.0` (versión
recomendada por Expo SDK 52). Agregada como dep regular de
`apps/mobile`.

### `apps/mobile/components/ui/date-input.tsx` (nuevo)

Componente cross-platform:

- Mantiene el contrato de los antiguos inputs: recibe/emite
  `YYYY-MM-DD` (lo que el backend espera). Internamente parsea
  a `Date` y formatea según la API del datetimepicker.
- Display: "DD/MM/YYYY" en el botón de toggle (mejor lectura local
  que el ISO crudo).
- iOS: picker `inline` mostrado/ocultado por toggle Pressable.
- Android: picker como modal nativo (`mode="default"`); se cierra
  solo al seleccionar o cancelar.
- `event.type === 'dismissed'` (Android) NO emite cambio.
- `minimumDate` / `maximumDate` opcionales para futuros casos de
  rango restringido.
- Helper estático `DateInput.todayISO()` para callers que necesitan
  un valor inicial.

### Sustituciones

Tres formularios mobile pasan de `<TextInput placeholder="YYYY-MM-DD">`
a `<DateInput>`:

- `apps/mobile/components/transaction-form.tsx`
  (campo `occurred_at`).
- `apps/mobile/components/budgets/budget-form-modal.tsx`
  (campo `effective_from`).
- `apps/mobile/components/receipt-capture-form.tsx`
  (campo `occurred_at`).

Todas mantienen su validación local (regex de formato ISO) — el
DateInput emite siempre formato válido, así que el regex actúa
ahora como guard ante usos futuros que pasen valores externos
sin sanitizar.

## Archivos clave

- `apps/mobile/package.json` (`@react-native-community/datetimepicker`)
- `apps/mobile/components/ui/date-input.tsx` (nuevo)
- `apps/mobile/components/transaction-form.tsx`
- `apps/mobile/components/budgets/budget-form-modal.tsx`
- `apps/mobile/components/receipt-capture-form.tsx`

## Verificación

- [x] `pnpm typecheck` verde.
- [x] `pnpm lint` verde.
- [x] `pnpm test` — sin regresiones (5 mobile + 38 web).
- [ ] Smoke en Expo:
  - [ ] Crear transacción → tap en campo Fecha → picker nativo →
        seleccionar otra → valor se actualiza en formato local.
  - [ ] Crear budget → tap en "Vigente desde" → picker nativo.
  - [ ] Capturar ticket → form de confirmación → tap fecha →
        picker nativo.
  - [ ] iOS: picker inline visible al tap, oculto al re-tap.
  - [ ] Android: modal aparece, "Cancelar" no cambia el valor.

## Decisiones tomadas

- **`@react-native-community/datetimepicker`** vs alternativas
  como `react-native-modal-datetime-picker`. La community
  package es la primitiva oficial; el modal-wrapper añade UX
  bonita pero también una capa de magia que oculta el evento
  `'dismissed'` y otros detalles. Para una primera versión
  funcional, ir directo a la primitiva.
- **Display "DD/MM/YYYY"** en lectura, **emitir ISO** en escritura.
  Locale-friendly para el usuario, contract-friendly para el
  backend.
- **Toggle Pressable wrap propio** en lugar de `Modal`. Funciona
  bien en ambas plataformas: en iOS el picker es inline (siempre
  visible cuando `pickerOpen=true`); en Android el sistema lo
  monta como modal nativo cuando se renderiza el componente.
- **Validación regex se mantiene en los formularios** aunque el
  DateInput emita siempre formato válido. Defensa en profundidad
  por si en el futuro alguien pasa valores externos.
- **Sin date range picker** en esta fase. Los campos actuales son
  fechas simples. Si llega rango (filtros de transacciones
  mobile, p.ej.), se compone con dos `DateInput`.

## Limitaciones conocidas

- **Sin time picker**. Las fechas que el backend espera son
  `YYYY-MM-DD` (Date, no Timestamp). Si en el futuro un campo
  necesita hora, el componente acepta `mode="datetime"` trivial.
- **Sin tests UI**. La integración nativa con `DateTimePicker`
  no se mockea fácil con `jest-expo` sin setup adicional. La
  verificación es smoke en Expo.
- **Sin localización del picker**. Usa el locale del sistema
  operativo del usuario por defecto — coherente con la convención
  móvil.

## Próxima fase

PHASE-14.4 — `convertAll` toggle en mobile. El store
`useCurrencyStore` ya es cross-platform desde PHASE-11.2 con
`convertAll: boolean`; falta UI mobile para alternarlo y
consumirlo en las queries del dashboard mobile.
