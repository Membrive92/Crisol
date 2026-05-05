# PHASE-11.2 — `useCurrencyStore` cross-platform

**Estado**: ✅ completada
**Rama**: `feat/phase-11.2-currency-store-cross-platform`
**PR**: —
**Fecha de merge**: 2026-05-05

## Objetivo

`useCurrencyStore` (Zustand persist con `localStorage` directo) era
web-only. Mobile no podía importarlo sin que React Native crashease
al evaluar `localStorage`. Resultado: cada pantalla mobile tenía
`useState(currency)` local — la moneda no se persistía entre
sesiones ni se compartía entre Análisis y futuras pantallas.

Esta fase introduce un adapter de storage cross-platform usando
**extensiones de plataforma de Metro** (`.native.ts` resuelve
automático en mobile, `.ts` plano en web/Next), y migra
`AnalysisScreen` mobile a consumir el store.

Pre-requisito para que mobile herede el toggle global `convertAll`
en una fase futura.

## Qué se implementó

### Capa shared

- **`packages/store/src/storage.ts`** (nuevo, web/Next default):
  `createJSONStorage(() => localStorage)` con guard SSR (`typeof
  window === 'undefined'` → storage `undefined`, evita crashes en
  Node). Tipo `PersistStorage<unknown>` para que el persist genérico
  no se queje del unknown del shape al construirse.
- **`packages/store/src/storage.native.ts`** (nuevo, Metro auto):
  `createJSONStorage(() => AsyncStorage)`. Metro escoge esta
  variante automáticamente para iOS/Android sin configuración
  adicional — `.native.ts` está en su `resolver.sourceExts` por
  defecto.
- **`packages/store/src/currency.ts`**: ahora importa `storage`
  de `./storage` (en lugar de envolver `localStorage` inline). El
  resto del store (estado, version=1, migrate) intacto — la
  persistencia previa en web sigue siendo compatible (mismo
  `name: 'finanzas:currency'`, mismo schema).
- **`@react-native-async-storage/async-storage` ^3.0.2** añadido
  como dep regular de `packages/store`. Web nunca llega a importar
  `storage.native.ts`, así que el bundler de Next jamás resuelve
  AsyncStorage — pesa 0 en el bundle web.

### Mobile

- **`apps/mobile/app/(modules)/personal-finance/(tabs)/analysis.tsx`**:
  el `useState(FALLBACK_CURRENCY)` local se reemplaza por
  `useCurrencyStore`. La hidratación inicial (sincronizar con la
  primera moneda real del usuario si la persistida no está) se
  mantiene pero ahora respeta la selección persistida del store —
  sólo sobrescribe si la moneda guardada NO está en
  `useUserCurrencies`.

### Resolución de bundlers

| Bundler | Archivo escogido | Cuándo |
|---------|------------------|--------|
| Metro (Expo iOS/Android) | `storage.native.ts` | siempre — `.native.ts` está en `resolver.sourceExts` por defecto. |
| Webpack (Next.js / web) | `storage.ts` | siempre — webpack no conoce `.native.ts` y resuelve la extensión más cercana. |
| Vitest (jsdom) | `storage.ts` | igual que webpack. Los tests web ven el adapter web. |

No hace falta configurar `metro.config.js` ni `next.config.mjs` —
el patrón es idiomático y funciona out-of-the-box.

## Flujo técnico

```
 Web (Next.js):
    import { storage } from './storage'
        │
        ▼ webpack: ./storage.ts
        ▼
    createJSONStorage(() => {
      if (typeof window === 'undefined') return undefined; // SSR
      return localStorage;
    })

 Mobile (Expo + Metro):
    import { storage } from './storage'
        │
        ▼ Metro detecta '.native.ts' y prefiere
        ▼
    createJSONStorage(() => AsyncStorage)

 currency.ts (mismo en ambas plataformas):
    create(persist(..., { name, storage, version, migrate }))
        │
        ▼ usa el storage adecuado al bundler
```

## Archivos clave

- `packages/store/package.json`
  (`@react-native-async-storage/async-storage` dep)
- `packages/store/src/storage.ts` (nuevo, web/Next)
- `packages/store/src/storage.native.ts` (nuevo, Metro)
- `packages/store/src/currency.ts` (importa el adapter, doc actualizada)
- `apps/mobile/app/(modules)/personal-finance/(tabs)/analysis.tsx`
  (consume `useCurrencyStore` en lugar de `useState` local)

## Endpoints

Ninguno.

## Migraciones

Ninguna (BD). El schema persistido en cliente sigue en `version: 1`
— web mantiene compatibilidad con datos previos.

## Verificación

- [x] `pnpm typecheck` verde (web + mobile + packages).
- [x] `pnpm lint` verde.
- [x] `pnpm test` — 20/20 web (sin cambios en suite, no añadimos
      tests aquí — ver decisión).
- [ ] Smoke manual:
  - [ ] Web: cambiar moneda en el header → recargar → moneda
        persiste (sin regresión).
  - [ ] Mobile: cambiar moneda en CurrencyPicker de Análisis →
        cerrar app → reabrir → moneda persiste.
  - [ ] Mobile: la primera vez con un usuario nuevo (sin
        AsyncStorage previo) → arranca en EUR, se reajusta a la
        primera moneda real del usuario tras la query
        `useUserCurrencies`.

## Decisiones tomadas

- **Extensión `.native.ts` en lugar de detección runtime**. La
  alternativa (`if (navigator.product === 'ReactNative') require(...)`)
  obliga al bundler web a intentar resolver el módulo nativo
  (falla salvo que esté instalado) y/o a mantener un try/catch.
  La extensión de plataforma es estándar Metro, gratis en Next/Vite
  (no la conocen) y no requiere config en ningún bundler.
- **`@react-native-async-storage/async-storage` como dep regular
  de `packages/store`**, no peer dep ni opcional. Pnpm lo resuelve
  para mobile (lo necesita) y webpack en web nunca llega a
  importarlo (extensión `.native.ts` no se evalúa). Cero coste en
  el bundle web.
- **No bumpamos `version`**. El schema serializado del store sigue
  igual (`{ currency, convertAll }`). La persistencia web previa
  funciona idéntica. Mobile arranca en blanco la primera vez —
  comportamiento esperado, no es una migración.
- **Sin tests vitest aquí**. El adapter es 7 líneas envolviendo
  `createJSONStorage` con guard SSR. Setup de vitest en
  `packages/store` (no lo tiene) por un test trivial añade más
  ruido del valor que aporta. La verificación es smoke manual y
  typecheck cruzado entre las dos extensiones.
- **Mobile sólo migra `analysis.tsx` en esta fase**. El
  `transactions.tsx` mobile no usa una moneda global hoy (cada fila
  formatea con su propia `tx.currency`). No introducir consumidores
  nuevos hasta que haga falta.
- **Hidratación: sólo sobrescribir si la moneda persistida NO está
  en las del usuario**. Antes el `useState(FALLBACK_CURRENCY)` se
  inicializaba siempre y el effect lo cambiaba si era necesario.
  Ahora el store viene con la moneda persistida — si es válida
  para este usuario, no se toca; si no (cambió de cuenta, dataset
  nuevo), se reajusta.

## Limitaciones conocidas

- **`useCurrencyStore` en mobile sólo se consume en `analysis.tsx`**.
  Otras pantallas (transactions, trash, future ones) podrán
  consumirlo cuando aporten lógica que necesite la moneda global.
- **Sin selector de `convertAll` en mobile**. El toggle global
  vive en el header web (`CurrencyMenu`). Mobile no tiene aún UI
  para alternarlo — y tampoco tiene lógica que lo use (el
  dashboard mobile no aplica `target_currency`). Cuando se priorice
  cross-currency en mobile, añadir el toggle en el header de
  Análisis o como switch en CurrencyPicker.
- **AsyncStorage es asíncrono — el primer paint mobile usa el
  default antes de hidratar**. Patrón estándar de Zustand persist
  con storage async; visible como un flicker minúsculo en el
  primer render. Si molesta: añadir `onRehydrateStorage` para
  retrasar el render hasta hidratación completa.
- **No hay tests del adapter** (decidido). Si en una fase futura
  packages/store gana otros stores con persistencia, vale la pena
  introducir vitest aquí.

## Próxima fase

PHASE-11.3 — Sistema de toasts global. El banner web
(`TrashedBanner`) y el snackbar mobile (`TrashedSnackbar`) son
ad-hoc para la pantalla de transacciones. Otros flujos (imports,
receipts) siguen sin feedback. Una API común reduce duplicación y
permite que próximos features no reinventen la rueda.
