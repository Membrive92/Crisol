# PHASE-14.4 — `convertAll` toggle en mobile

**Estado**: ✅ completada
**Rama**: `feat/phase-14.4-mobile-convert-all`
**Fecha de merge**: 2026-05-05

## Objetivo

Cierre del último cabo del store cross-platform: `useCurrencyStore`
desde PHASE-11.2 ya tenía `convertAll: boolean` persistido pero
mobile sólo consumía `currency`. Esta fase añade UI para alternar
el toggle en Análisis y conecta las queries del dashboard al
mismo flujo cross-currency que web (`target_currency`
→ backend convierte cada tx con la tasa de su día).

## Qué se implementó

`apps/mobile/app/(modules)/personal-finance/(tabs)/analysis.tsx`:

- Añade `convertAll` y `setConvertAll` desde `useCurrencyStore`.
- Construye `summaryParams`, `monthlyParams`, `byCategoryParams` y
  `topExpensesParams` ramificando entre `target_currency`
  (cross-currency) y `currency` (legacy) según el toggle. Misma
  lógica que la página web `/analysis`.
- Añade `<View styles.currencyRow>` que envuelve el `CurrencyPicker`
  y un `Pressable` chip "Convertir todo" con check visual cuando
  está ON (palette primarySoft + primary). `accessibilityRole="switch"`
  + `accessibilityState={{ checked }}` para screen readers.

Sin cambios en hooks, packages shared ni backend.

## Archivos clave

- `apps/mobile/app/(modules)/personal-finance/(tabs)/analysis.tsx`

## Verificación

- [x] `pnpm --filter @finanzas/mobile typecheck` verde.
- [x] `pnpm --filter @finanzas/mobile lint` verde.
- [ ] Smoke en Expo:
  - [ ] Análisis con convertAll OFF → KPIs filtran sólo
        transacciones de la moneda activa.
  - [ ] Tap chip → ON → KPIs ahora suman cross-currency
        convirtiendo a la moneda activa con la tasa por día.
  - [ ] Cerrar la app → reabrir → toggle persiste
        (PHASE-11.2 store + AsyncStorage).

## Decisiones tomadas

- **Chip pill simple en lugar de Switch nativo**. RN `Switch`
  aporta el control nativo pero ocupa altura fija ~30px y
  visualmente compite con los chips del CurrencyPicker. Un
  Pressable estilo pill se integra mejor con el resto de chips
  de la pantalla (PeriodToggle, CurrencyPicker).
- **`accessibilityRole="switch"`** y `accessibilityState.checked`.
  El comportamiento es de toggle, no de botón ordinario; los
  screen readers anuncian "Activado / Desactivado".
- **No expongo `convertAll` en otras pantallas mobile**. Análisis
  es el único consumer de las queries de dashboard. Si llegan
  otras (Transacciones mobile con conversión per-row, p.ej.),
  añadirlo allí.
- **Branching de params explícito** (4 ifs) en lugar de un
  spread genérico. Es más verboso pero claro al leer y empareja
  el patrón de la página web. Refactor futuro a un helper si
  llegan más callers.

## Limitaciones conocidas

- **Sin tests UI**. Heredado.
- **Mobile transactions tab no aplica convertAll** todavía. La
  pestaña no muestra conversiones per-row (web sí lo hace desde
  PHASE-8.4). Si emerge necesidad, añadir el patrón ahí.

## Próxima fase

PHASE-14.5 — Notificaciones proactivas de budget over.
Implementación: hook tras `transactions.create` que verifica los
budgets afectados y emite un toast si la categoría queda en `over`
tras la nueva transacción.
