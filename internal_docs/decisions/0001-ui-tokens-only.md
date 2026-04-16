# ADR-0001 — `packages/ui` arranca con design tokens, no componentes

**Estado**: aceptada
**Fecha**: 2026-04-16
**Fase**: PHASE-2.2

## Contexto

La skill `frontend-best-practices` describe un `packages/ui` con componentes
compartidos entre web y mobile. El plan original de PHASE-2.2 contemplaba
crearlo con componentes como `Button`, `Input`, `Card`.

Para que un mismo componente React se renderice en Next.js y React Native
hacen falta dos piezas:

1. **Bridging**: o bien instalar `react-native-web` y añadir
   `transpilePackages` en Next.js, o bien usar extensiones de plataforma
   (`.web.tsx` / `.native.tsx`). Ambas tienen costes no triviales.
2. **Styling común**: sin NativeWind/Tailwind, cada plataforma usa su
   sistema de estilos (inline en web, `StyleSheet` en mobile). Añadir
   NativeWind requiere tocar `metro.config.js`, `babel.config.js`,
   `tailwind.config.*` y dependencias.

Hacer ambos cambios dentro de PHASE-2.2 desborda su alcance (transacciones
frontend) y mete riesgo de build roto en dos apps a la vez.

## Decisión

`packages/ui` se crea con **solo design tokens** (colores, espaciado,
tipografía, radios) y **helpers de formato** sin dependencias de
plataforma (`formatAmount`, `formatDate`, conversores ISO ↔ input date).

Los componentes reales (`Button`, `Field`, `Card`, formularios,
listas…) viven por ahora en `apps/web/components/` y
`apps/mobile/components/`, consumiendo los tokens para mantener
consistencia visual entre plataformas.

## Consecuencias

- ✅ PHASE-2.2 queda acotada y entregable.
- ✅ Ambas apps siguen funcionando con su sistema de estilos actual sin
  retoques de build.
- ✅ La nomenclatura de tokens está establecida: cuando se migre a una
  librería unificada, los componentes ya hablan el mismo idioma.
- ⚠️ Hay duplicación inevitable entre `apps/web/components/transactions/`
  y `apps/mobile/components/` (unos 150 líneas de form + list). Aceptada
  temporalmente.
- 🔜 Se abrirá una fase dedicada a adoptar NativeWind + `react-native-web`
  cuando la app tenga más superficie y la duplicación empiece a doler de
  verdad. No antes de PHASE-3.

## Alternativas descartadas

- **NativeWind + `react-native-web` ahora**: desborda la fase, riesgo de
  regresiones en auth ya funcional.
- **Componentes con `.web.tsx` / `.native.tsx` sin NativeWind**: aporta
  la fricción del bridging sin el beneficio del styling unificado.
- **No crear `packages/ui` en absoluto**: se pierde la oportunidad de
  centralizar los tokens y los formatters, que sí son fácilmente
  reutilizables hoy.
