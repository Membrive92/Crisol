# PHASE-29 — Refactor visual Análisis + chrome global (copper brand)

**Estado**: ✅ completada
**Rama**: `main` (commits directos)
**Fecha de merge**: 2026-05-25

## Objetivo

Implementación del handoff de Claude Design
(`design_handoff_crisol_analisis/`) que resuelve tres problemas
acumulados:

1. **Duplicación de información** entre `BalancesCard` y
   `DebtHealthCard` — ambas mostraban patrimonio neto + activos +
   pasivos como cifra grande.
2. **Chrome poco distintivo** — items de navegación pequeños sin
   icono, header genérico, brand mark perdido.
3. **Brand identity confusa** — el logo es naranja pero el primary
   token era azul (`#1976d2`), generando dos acentos compitiendo
   en pantalla.

## Qué se implementó (commits por sub-fase)

### PHASE-29.1 — Copper brand tokens

Cambio del primario de azul a cobre, alineado con el logo. Mantiene
el resto de la paleta (success/danger/warning/income/expense/
surfaces). Sincroniza los fallbacks de RN (`packages/ui/src/tokens.ts`)
y la documentación del sistema (`DESIGN.md`).

| Token | Light antes → ahora | Dark antes → ahora |
|---|---|---|
| `primary` | `#1976d2` → `#c4671f` | `#2f6fb8` → `#e07a3a` |
| `primary-dark` | `#115293` → `#8b461a` | `#245690` → `#a85820` |
| `on-primary` | `#f7f9fc` → `#fff8f0` | `#f4f7fb` → `#1a0e05` |
| `primary-soft` | `#e3eefb` → `#fdf0e6` | `#1d2a3d` → `#3a2418` |

### PHASE-29.2 — Sidebar refactor

- Brand: `<img>` favicon → inline `BrandDot` (radial-gradient
  cobre, 24×24).
- Items agrupados bajo overlines "ESPACIO" / "PRÓXIMAMENTE"
  (eliminado el `module-switcher` chip redundante).
- Cada item con `ico-wrap` 30×30 (un cuadrito tonal que se rellena
  de `primary-soft` + copper al hover/active).
- Estado activo: bar copper 3px en el borde izquierdo (vía
  `<span>` absolutamente posicionado, no `::before` — usamos inline
  styles).
- Iconos por módulo: `LayoutDashboard`, `Wallet`, `HeartPulse`,
  `BarChart3`, `TrendingUp`, `Home`.
- CTA "Añadir transacción": gradient copper, 3 columnas
  (`+` rotativo / label + subtítulo / kbd "N"), shadow amplificada
  en hover. Atajo `n` no cableado todavía (TODO).
- Footer caption "Datos en este dispositivo".

### PHASE-29.3 — Header chrome

- `IconButton`: hover ahora ilumina el icono en cobre (era texto
  neutro). Press: `scale(.94)`.
- Bell con dot 7×7 `danger` (border 2px en `background` para
  cortar contra el icono). Dot encendido siempre por ahora —
  cuando haya canal de notificaciones se conectará a un
  `useUnread`.
- Nuevo `HeaderDivider` (1×24) entre grupos: bell | currency +
  theme | user.
- `CurrencyMenu` trigger: `CurrencyPillTrigger` (cuadradito 26×26
  con símbolo `€` en `primary-soft` que pasa a `primary` al
  hover + código en 13/600 tabular + chevron). Glow tonal
  `box-shadow: primary-soft`.
- `UserMenu` trigger: `UserChipTrigger` (avatar 30×30 con
  iniciales sobre gradient copper + nombre + "Personal" como
  rol). Mismo patrón de glow.

### PHASE-29.4 — Section tabs

- Cada tab lleva ahora icono por section key
  (`analysis→BarChart3`, `transactions→Receipt`,
  `budgets→Target`, `fixed-expenses→Repeat`,
  `transfers→ArrowLeftRight`).
- Nuevos iconos `TargetIcon` (círculos concéntricos) y
  `RepeatIcon` (loop arrows) en `icons.tsx`.
- Estado activo: subrayado copper 2px en `bottom: -9px` (queda
  sobre el `borderBottom` del header). Sustituye al pill
  primary-soft que teníamos.
- Hover unificado en `surface-muted` (sin tinte azul para
  diferenciarlo del activo) — el subrayado carga el signal del
  estado activo.
- Prop `counts?: Partial<Record<sectionKey, number>>` opcional
  para pintar un badge (18×18 pill) a la derecha del label.
  El layout aún no lo pasa — la API queda lista para que un
  follow-up enchufe `useTransactions().total` y
  `useFixedExpenses().total` sin más refactor.

### PHASE-29.5 — `PositionHero` (componente nuevo)

`apps/web/components/analysis/position-hero.tsx` — fusiona en una
única `Card` la información que vivía en `BalancesCard` +
`DebtHealthCard`. Tres secciones:

- ① Patrimonio neto: bubble + overline + cifra display + warning
  cross-currency (si aplica) + composition bar de cuentas activas
  (split proporcional assets ↔ liabilities con sub-slices por
  cuenta separados por 2px `surface`).
- ② Salud de deuda: bubble + overline + chip DTI status + DTI
  big + gauge bar (6px, con threshold markers 35%/60%) + grid 4
  KPIs (cuota mensual, APR medio, intereses YTD, % en deuda).
- ③ Cuentas activas: grid 3 columnas con swatch + nombre + balance.

Layout: `gridTemplateColumns: minmax(0,1.05fr) 1px minmax(0,1fr)`
para las secciones 1 y 2 (la columna del medio es el divider de
1px); la sección 3 va a pie. Media queries inline:
- `<960px`: las dos top stack, divider se oculta.
- `<640px`: grid de cuentas pasa a 1 columna.

`/personal-finance/analysis/page.tsx` usa `<PositionHero />` en
lugar de los dos cards. Las cards legacy
(`BalancesCard`, `DebtHealthCard`) **se conservan** porque siguen
siendo válidas en `/dashboard`.

Lo que NO incluye (follow-ups del handoff):
- Sparkline de trayectoria del net worth (no hay endpoint de
  serie temporal para patrimonio; sólo `debt-history` cubre
  liabilities).
- Δ chip vs periodo anterior.

### PHASE-29.6 — Polish de las cards del bento

`stitch-expense-breakdown.tsx` (donut):
- Centro hover-driven: con slice activo muestra
  `{label} · {value} · {pct}% del total`; sin hover muestra
  `Total · {amount}`. Transición opacidad/color 120ms.

`stitch-income-vs-expenses.tsx` (bar chart):
- Tooltip añade una tercera línea "Neto" debajo (separada por
  border-top 1px), coloreada según signo (income vs danger).
  Se calcula desde los `entries` sin asumir orden concreto.

`stitch-key-metrics.tsx`:
- Card "Flujo de caja neto": nueva mini sparkline al final.
  SVG dibujado a mano (12 puntos típicos) con gradient fill
  + último punto destacado + baseline punteada en y(0). Color
  según signo del cashflow total.
- Card "Tasa de ahorro": sustituida la barra lineal 0-100% por
  `CenteredRateBar` (50% = 0%, extiende a izquierda para
  negativos, derecha para positivos). Resuelve el caso del
  usuario con rate negativo (la barra antigua quedaba vacía).
  Ejes -100% / 0 / +100% debajo.

## Archivos clave

```
apps/web/app/globals.css                                          # tokens light/dark
packages/ui/src/tokens.ts                                          # RN fallbacks
DESIGN.md                                                          # design system doc
apps/web/components/modules/app-sidebar.tsx                        # refactor sidebar
apps/web/components/modules/module-sections.tsx                    # refactor tabs
apps/web/components/ui/icons.tsx                                   # +TargetIcon +RepeatIcon, export IconProps
apps/web/app/(app)/layout.tsx                                      # bell + dividers + IconButton polish
apps/web/components/header/currency-menu.tsx                       # pill trigger
apps/web/components/auth/user-menu.tsx                             # chip trigger con iniciales
apps/web/components/analysis/position-hero.tsx                     # NUEVO
apps/web/app/(app)/personal-finance/analysis/page.tsx              # adopta PositionHero + monthly→KeyMetrics
apps/web/components/analysis/stitch-expense-breakdown.tsx          # hover-driven center
apps/web/components/analysis/stitch-income-vs-expenses.tsx         # tooltip con Neto
apps/web/components/analysis/stitch-key-metrics.tsx                # sparkline + centered bar
```

## Verificación

- [x] Web typecheck verde tras cada sub-commit
- [x] Mobile typecheck verde (sólo se tocan tokens RN; sin cambios
      visuales mobile en esta fase)
- [x] 46/46 web tests
- [x] Manual: /analysis muestra PositionHero, sidebar con copper
      activo, header con pill/chip/dot, tabs con iconos
- [x] Manual: donut hover, tooltip Neto, sparkline, centered bar

## Limitaciones conocidas

- Mobile no recibe el refresh visual; sigue con el chrome
  anterior (sólo cambian los tokens, así que cualquier elemento
  que use `colors.primary` se verá copper también allí).
- El atajo `n` para "Nueva transacción" no está cableado a un
  listener global. El `kbd` del CTA es signage de la intención.
- Section tabs no consumen counts todavía (la prop existe).
- Net-worth trajectory sparkline y Δ chip quedaron fuera por
  falta de endpoint de serie temporal.

## Próximas tareas opcionales

- PHASE-29.7: cablear counts en section tabs.
- PHASE-29.8: añadir endpoint `GET /accounts/balances/history` y
  encender la sparkline de trayectoria del net worth en
  PositionHero.
- PHASE-29.9: parity mobile del nuevo chrome.
