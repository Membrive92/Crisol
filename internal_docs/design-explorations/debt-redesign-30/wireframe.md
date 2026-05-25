# Wireframe textual — `/debt` rediseñada (PHASE-30)

> Documento de referencia visual para la implementación de PHASE-30.3.
> No es maquetación final — describe jerarquía, dependencias de datos
> y comportamiento. La implementación se ciñe a tokens de
> `DESIGN.md` (copper brand) y no introduce nuevos primitivos.

---

## Vista global — usuario con liabilities

```
╔═════════════════════════════════════════════════════════════════╗
║  DEUDA                                                          ║
║  Tasa de esfuerzo · €1.234 al mes sobre €3.500 netos            ║
║                                                  [Añadir deuda] ║
╠═════════════════════════════════════════════════════════════════╣
║                                                                 ║
║  ┌───────────────────────────────────────────────────────────┐  ║
║  │  TASA DE ESFUERZO                  [Estricta] [Ampliada]  │  ║
║  │                                                           │  ║
║  │       35.2%                                  [Atención]   │  ║
║  │                                                           │  ║
║  │  0%      30%      35%      50%                            │  ║
║  │  ────────│●───────│────────────                           │  ║
║  │          └ Saludable                                      │  ║
║  │                                                           │  ║
║  │  ⓘ % de tus ingresos netos mensuales que va a cuotas      │  ║
║  │    de deuda. Banco de España recomienda <35%.             │  ║
║  └───────────────────────────────────────────────────────────┘  ║
║                                                                 ║
║  ┌───────────────────────────────────────────────────────────┐  ║
║  │  PAGOS A DEUDA              [YTD ▾]  Año en curso         │  ║
║  │                                                           │  ║
║  │  €11.840                                                  │  ║
║  │                                                           │  ║
║  │  ┌───── Intereses y comisiones ─────┐ ┌── Capital ──┐    │  ║
║  │  │  €2.340 (19.8%) — coste real     │ │  €9.500     │    │  ║
║  │  └──────────────────────────────────┘ └─────────────┘    │  ║
║  │  ▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░     │  ║
║  │  ⓘ Capital amortizado: sale de tu bolsillo pero          │  ║
║  │    reduce la deuda pendiente, construye patrimonio.       │  ║
║  └───────────────────────────────────────────────────────────┘  ║
║                                                                 ║
║  ┌─────────────────────────┐  ┌──────────────────────────────┐ ║
║  │  COMPOSICIÓN            │  │  EVOLUCIÓN MENSUAL  ─12m─    │ ║
║  │                         │  │                              │ ║
║  │       ╭───╮             │  │     ▆ ▆ ▆ ▆ ▆ ▆ ▆ ▆ ▆ ▆ ▆ ▆ │ ║
║  │      ╱     ╲            │  │     ▇ ▇ ▇ ▇ ▇ ▇ ▇ ▇ ▇ ▇ ▇ ▇ │ ║
║  │     │  70% │ Hipoteca   │  │     ▇ ▇ ▇ ▇ ▇ ▇ ▇ ▇ ▇ ▇ ▇ ▇ │ ║
║  │      ╲     ╱            │  │     J F M A M J J A S O N D │ ║
║  │       ╰───╯             │  │     ─── intereses (▆)        │ ║
║  │   20% Tarjeta · 10% Pr. │  │     ─── capital   (▇)        │ ║
║  │                         │  │     ↑ mes actual             │ ║
║  └─────────────────────────┘  └──────────────────────────────┘ ║
║                                                                 ║
║  ┌───────────────────────────────────────────────────────────┐  ║
║  │  CUOTAS RECURRENTES DETECTADAS                            │  ║
║  │                                                           │  ║
║  │  ⊙ Hipoteca BBVA       · €850/mes · Categoría: Hipoteca  │  ║
║  │     Próxima: 1 jun. · Vinculada a contrato BBVA          │  ║
║  │                                                           │  ║
║  │  ⊙ Tarjeta Visa CaixaB · €120/mes · Categoría: Tarjeta   │  ║
║  │     Próxima: 5 jun. · Sin contrato vinculado [Vincular]  │  ║
║  └───────────────────────────────────────────────────────────┘  ║
║                                                                 ║
║  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   ║
║                                                                 ║
║  DETALLE POR CONTRATO · 2 contratos activos             [▾]    ║
║                                                                 ║
║  ┌───────────────────────────────────────────────────────────┐  ║
║  │ 🏦 Hipoteca BBVA            -€138.500    [DEUDA]          │  ║
║  │    HIPOTECA · 2.45% TIN · Cuota €850 · 180 meses restantes│  ║
║  │    Categoría vinculada: Hipoteca                          │  ║
║  │                              [Pagar cuota] [Ver cuadro →] │  ║
║  ├───────────────────────────────────────────────────────────┤  ║
║  │ 💳 Tarjeta Visa             -€1.240      [DEUDA]          │  ║
║  │    CREDIT_CARD · 18.5% TIN · Pago mín. estimado €37       │  ║
║  │    Sin categoría vinculada                                │  ║
║  │                              [Pagar cuota] [Ver cuadro →] │  ║
║  └───────────────────────────────────────────────────────────┘  ║
║                                                                 ║
║  ┌───────────────────────────────────────────────────────────┐  ║
║  │  EVOLUCIÓN DE LA DEUDA TOTAL (Capa 2)        ─12m ↔ +12m─ │  ║
║  │                                                           │  ║
║  │  €200k ╮                                                  │  ║
║  │        ╲                                                  │  ║
║  │  €150k  ╲─────────────────·····                           │  ║
║  │                            ····                           │  ║
║  │  €100k                       ·····                        │  ║
║  │        Histórico│ ahora │ Proyectado (cuotas teóricas)    │  ║
║  └───────────────────────────────────────────────────────────┘  ║
╚═════════════════════════════════════════════════════════════════╝
```

## Vista global — usuario sin liabilities pero con categoría de deuda

```
╔═════════════════════════════════════════════════════════════════╗
║  DEUDA                                                          ║
║  Tasa de esfuerzo · €970 al mes sobre €3.500 netos              ║
║                                                                 ║
║  ┌───────────────────────────────────────────────────────────┐  ║
║  │  TASA DE ESFUERZO                  [Estricta] [Ampliada]  │  ║
║  │                                                           │  ║
║  │       27.7%                                 [Saludable]   │  ║
║  │                                                           │  ║
║  │  0%   30%   35%   50%                                     │  ║
║  │  ────●│─────│──────                                       │  ║
║  └───────────────────────────────────────────────────────────┘  ║
║                                                                 ║
║  ┌───────────────────────────────────────────────────────────┐  ║
║  │  PAGOS A DEUDA              [YTD ▾]  Año en curso         │  ║
║  │                                                           │  ║
║  │  €5.820                                                   │  ║
║  │  └ Intereses y comisiones · €— (no desglosado en extracto)│  ║
║  │  └ Capital + intereses · €5.820                           │  ║
║  │  ⓘ Tu banco no desglosa intereses en el extracto. Para    │  ║
║  │    ver coste real exacto, vincula este contrato a una     │  ║
║  │    cuenta de deuda con TIN. [Vincular]                    │  ║
║  └───────────────────────────────────────────────────────────┘  ║
║                                                                 ║
║  [Composición + Evolución igual que arriba]                    ║
║                                                                 ║
║  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   ║
║                                                                 ║
║  DETALLE POR CONTRATO                                          ║
║                                                                 ║
║  ┌───────────────────────────────────────────────────────────┐  ║
║  │  💡 Para que tu patrimonio neto refleje toda tu deuda,    │  ║
║  │     vincula un contrato a tus cuotas recurrentes.          │  ║
║  │                                                            │  ║
║  │     Hemos detectado:                                       │  ║
║  │     · Hipoteca BBVA · €485/mes · 12 meses observados      │  ║
║  │                                          [Crear contrato] │  ║
║  │                                                            │  ║
║  │     ⓘ Sin contrato vinculado, tu patrimonio neto solo     │  ║
║  │       cuenta los activos. La deuda real puede ser mayor.  │  ║
║  └───────────────────────────────────────────────────────────┘  ║
╚═════════════════════════════════════════════════════════════════╝
```

## Vista global — usuario sin deuda

```
╔═════════════════════════════════════════════════════════════════╗
║  DEUDA                                                          ║
║                                                                 ║
║  ┌───────────────────────────────────────────────────────────┐  ║
║  │                                                           │  ║
║  │            Sin pagos a deuda este año                     │  ║
║  │                                                           │  ║
║  │       Cuando categorices un pago como deuda o crees       │  ║
║  │       una cuenta de tipo préstamo / hipoteca / tarjeta,   │  ║
║  │       este panel se rellenará automáticamente.            │  ║
║  │                                                           │  ║
║  │             [Añadir cuenta de deuda]                      │  ║
║  │                                                           │  ║
║  └───────────────────────────────────────────────────────────┘  ║
╚═════════════════════════════════════════════════════════════════╝
```

---

## Dependencias de datos por sección

| Sección | Endpoint | Hook |
|---|---|---|
| Header (KPIs resumen) | `GET /debt/category-summary?range=month` | `useDebtCategorySummary('month')` |
| ① Tasa de esfuerzo | `GET /debt/category-summary?range=month` | mismo |
| ② Pagos a deuda | `GET /debt/category-summary?range=ytd\|12m\|month` | mismo, con `range` reactivo |
| ③ Composición | `GET /debt/category-summary?range=ytd` (campo `by_type`) | mismo |
| ④ Evolución mensual | `GET /debt/category-summary?range=12m` (campo `monthly_series`) | mismo |
| ⑤ Cuotas recurrentes | `GET /debt/category-summary` (campo `recurring_quotas`) | mismo |
| ⑥ Detalle contratos | `GET /accounts/balances` + `GET /accounts/?nature=liability` | `useAccountBalances`, `useAccounts` |
| Capa 2 evolución | `GET /accounts/debt-history` | `useDebtHistory` |

Una única query principal (`/debt/category-summary`) alimenta toda la
Capa 1. Capa 2 reusa endpoints existentes.

---

## Decisiones visuales clave

- **Sin segunda chromatic accent**. Mantenemos copper como único color
  de brand. Los KPI usan `success` / `warning` / `danger` solo en chips
  y gauges, nunca en chrome.
- **Tabular nums** (`font-variant-numeric: tabular-nums`) en todas las
  cifras monetarias.
- **`*-soft` tonal backgrounds** para chips de estado, jamás
  `rgba(color, 0.x)` runtime.
- **Composition donut** con segmentos separados por 2px `surface`
  (mismo patrón que PositionHero composition bar).
- **Bar chart de evolución** con barras apiladas (no agrupadas) —
  intereses abajo, capital arriba. Total visualmente comparable mes a
  mes.
- **Sin shadows en cards**. Layering por `surface` → `surface-muted`.
- **Empty states centrados**, con CTA primario único.
- **El divider entre Capa 1 y Capa 2** es una línea de 1px `border`
  con margen vertical generoso (xxl) — no un panel separado. La
  jerarquía la define el espacio.

## Responsiveness

| Breakpoint | Comportamiento |
|---|---|
| ≥1100px | Layout completo en columnas (composición + evolución en grid 2 cols). |
| 960-1099px | Grid 2 cols se mantiene. |
| 640-959px | Composición y evolución pasan a una sola columna apiladas. |
| <640px | Todo en una columna, paddings reducidos a `md`. |

Mismas media queries que `PositionHero` (`<960px` y `<640px`) para
coherencia. Inline `<style>` igual que el existente, no nuevos
mecanismos.

---

## Estados de carga y error

- **Loading**: skeleton con `colors.surfaceMuted` en cada card, 1.5s
  pulse animation. Si hay datos cacheados de la query anterior,
  mostrarlos en lugar del skeleton.
- **Error**: card individual muestra "Error cargando {sección}." en
  `colors.danger`. No tira la página entera.
- **Empty Capa 1** (usuario sin nada): el bloque de Capa 1 entero
  colapsa a un único empty state como en la tercera vista del wireframe.
- **Empty Capa 2** (no hay liabilities, sí hay cuotas detectadas):
  CTA "Crear contrato vinculado" como en la segunda vista.
- **Empty Capa 2** (no hay liabilities, no hay cuotas detectadas):
  no se renderiza la sección Capa 2 en absoluto. La página termina
  con las cuotas recurrentes.

---

## Notas para el implementador

1. La sección "Tasa de esfuerzo" debe ser **una pieza autocontenida**
   (`<EffortRatioSection />`) que puede reusarse en `PositionHero`
   sustituyendo al gauge DTI actual. Reducir duplicación de lógica.
2. El desglose intereses/capital en "Pagos a deuda" debe **animar la
   barra horizontal** al toggle YTD/12M/Mes (transición width 200ms,
   `ease-standard` token).
3. El donut "Composición" debe permitir **click en segmento → filtrar
   evolución a ese tipo** (interacción opcional, follow-up si
   desborda 30.3).
4. Los chips "Estricta" / "Ampliada" arriba del gauge actúan como
   **segmented control**, no como toggle binario. Patrón:
   ```
   ┌────────────┬────────────┐
   │ Estricta ▼ │  Ampliada  │
   └────────────┴────────────┘
   ```
   El activo lleva `surface-muted` background; el inactivo
   `transparent`. Border copper en el activo.
5. El componente "Cuotas recurrentes detectadas" debe **degradar
   correctamente** si `fixed_expenses` no tiene matches — colapsa a 0
   altura, no muestra título vacío.
6. La sección Capa 2 debe poder colapsarse con `<details>` HTML
   nativo en una primera iteración. Si UX pide animación, se sustituye
   por un `useState` + transición de altura controlada.
