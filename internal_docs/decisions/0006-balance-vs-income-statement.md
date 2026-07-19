# ADR-0006 — Dashboard = balance (stocks), Análisis = cuenta de resultados (flujos)

**Estado**: aceptado — implementación por fases. Backend de la métrica hecho
(PHASE-43.1 ventana de recurrencia + 43.2 override/explicabilidad, ambos en
verde); el **reparto de superficies** (43.3–43.5) y el **contrato de agregación**
están pendientes.
**Fecha**: 2026-07-18
**Depende de**: [ADR-0004](0004-transaction-level-money-truth.md) (`transactions.flow`
como fuente de verdad del dinero) · contexto en
[PHASE-37](../phases/phase-37-analysis-redesign.md) y
[PHASE-41](../phases/phase-41-module-simplification.md)
**Ámbito**: reparto de responsabilidades entre `/dashboard`,
`/personal-finance/analysis` y `/debt` (web + móvil) + un contrato de agregación
por módulo. Sin migración destructiva. Plan ejecutivo en
[`improvements/phase-43-dashboard-analysis-split.md`](../improvements/phase-43-dashboard-analysis-split.md).

## Contexto

`/dashboard` y `/personal-finance/analysis` responden hoy **la misma pregunta con
componentes distintos**. Consumen los mismos hooks (`useDashboardSummary`,
`useDashboardByCategory`, `useDashboardByMonth`, `useAccountBalances`) y
`/analysis` es un **superconjunto estricto**: añade `useDebtHealth`,
`useExpenseStructure`, `usePositionHistory`, `useMonthOutlook`, `usePositionAsOf`.
Ambas pintan patrimonio neto, ingresos/gastos del periodo, desglose por categoría,
evolución mensual y navegador de periodo. Es duplicación real, no dos vistas
complementarias.

Además, el "módulo global de agregación" vive físicamente en
`backend/app/modules/personal_finance/dashboard/` y sus 7 endpoints son **todos**
métricas de finanzas domésticas. El comentario del registry (*"combina ingresos
y gastos de TODOS los módulos verticales"*) es una **aspiración, no una
descripción**: hoy sólo existe un vertical (`personal-finance`); inversión y
bitcoin están diseñados pero no implementados.

El problema no es que falte una vista; es que **no hay una línea que diga qué
pregunta contesta cada superficie**, así que cada card nueva se coloca donde cae
y las dos páginas convergen.

## Decisión

**Cada página responde una pregunta y una sola**, siguiendo la separación
contable con 500 años de historia entre balance (lo que tienes en un instante) y
cuenta de resultados (lo que entró y salió en un periodo):

| Página | Pregunta | Naturaleza | Equivalente contable |
|---|---|---|---|
| `/dashboard` | *"¿Cuánto valgo?"* | **Stocks** | Balance |
| `/personal-finance/analysis` | *"¿En qué gasté y cuánto ahorré?"* | **Flujos** | Cuenta de resultados |
| `/debt` | *"¿Cómo va mi deuda?"* | Detalle | Notas |

### Por qué el patrimonio pertenece al dashboard (y no a Análisis)

`patrimonio neto = activos − pasivos` **cruza módulos**. Hoy son finanzas + deuda;
mañana + inversión + bitcoin + inmuebles. **Ningún vertical puede calcularlo por
sí solo** — sólo el agregador que ve todas las carteras. Es la única métrica que
*legítimamente pertenece* al dashboard y la razón por la que el dashboard debe
existir como superficie propia en vez de ser un alias de Análisis.

De aquí sale una consecuencia sobre la definición de ahorro que resuelve la
duplicación: **el ahorro en Análisis es un FLUJO del periodo** (`ingresos −
gastos`); el **ahorro acumulado es un STOCK** y ya está contenido en el
patrimonio, que vive en el dashboard. Por eso Análisis pierde
`NetworthEvolutionCard` (evolución del patrimonio = stock → dashboard) sin perder
información: es la misma verdad contada en el sitio correcto.

### Regla dura para las cards del dashboard

Una card de módulo en el dashboard es **veredicto + un número + un link**. No un
mini-módulo. Ejemplo canónico:

```
💳 Deuda      −19.500 €      esfuerzo 10,3 % · saludable      →
```

Si `DebtSummaryCard` se mudara tal cual (esfuerzo + cuota + APR + lista de
movimientos), se **movería el problema** en vez de resolverlo. El modo de fallo
del "dashboard de portfolio" es acabar siendo un **muro de todo que no contesta
nada**, porque cada módulo quiere su rincón y nadie dice que no. Esta regla es
el "no".

**El link es lo que hace que quitar detalle no sea perderlo.** En el dashboard la
deuda es un stock de un vistazo (deuda viva + veredicto de salud); en cuanto la
pregunta cambia a *"¿qué pagué este mes?"*, *"¿cuánto capital me queda?"* o
*"¿cuándo es la próxima cuota?"*, eso ya es otra pregunta y su sitio es `/debt`.
La flecha `→` es el puente entre las dos. Y `/debt` **ya existe** con ese detalle
(cuadro de amortización, KPIs, contratos): el reparto no construye un destino
nuevo, sólo retira del dashboard la *copia* del detalle que ya vive donde debe —
quita superficie, no la añade.

**Criterio para decidir qué entra en una card del dashboard**: si un dato necesita
que lo mires más de un segundo, no es de dashboard, es del módulo. Deuda viva +
veredicto pasan el filtro; la lista de movimientos, el APR y la cuota no. Esto
descompone `DebtSummaryCard` **por naturaleza** (no la reubica): su resumen-stock
se colapsa a una línea aquí, su detalle-flujo se absorbe en `/debt`.

### Los pagos de deuda no son una categoría contable homogénea → van a `/debt`

*"Pagos de deuda"* mezcla dinero de distinta naturaleza y por eso no cabe ni en
el balance ni en la cuenta de resultados:

| Línea | `flow` | ¿Es gasto? |
|---|---|---|
| `CARGO AMORTIZACIÓN PRÉSTAMO` | `OUT` | **Sí** |
| `ADEUDO MENSUAL DE TARJETA` | `TRANSFER_OUT` | **No** (ya contado compra a compra) |
| Cuota de operación financiada | `TRANSFER_OUT` | **No** |

La mitad son gasto y la otra mitad movimientos neutros. No puede ir a `/analysis`
(contradiría la narrativa de gastos) ni es un KPI de balance. Es **trazabilidad
de deuda** → su sitio es `/debt`, junto al cuadro de amortización, donde la
pregunta *"¿cuánto llevo pagado y cuándo?"* tiene sentido.

## Contrato de agregación (prepara los verticales futuros)

El dashboard **compone, no calcula** — salvo el patrimonio consolidado, que es
suyo por definición. Cada vertical expone su propio resumen:

```
GET /{module}/dashboard-summary
→ {
    verdict:        "healthy" | "caution" | "stressed" | "neutral",
    headline_value: Decimal,
    headline_label: str,
    secondary:      [{ label: str, value: str }],
    link:           str
  }
```

El dashboard pinta una card por módulo a partir de ese contrato. Cuando llegue
inversión, **su card sale sola sin tocar el dashboard** — implementa el endpoint
al nacer. Es el diseño que el registry ya prometía y que hoy no existe.

**MVP**: implementarlo para `debt` y `personal-finance`. Los verticales futuros
lo implementan al nacer.

## Qué se mueve a dónde

| Elemento (hoy en Análisis) | Destino |
|---|---|
| Tile `Patrimonio neto` + `Δ patrimonio` | Dashboard |
| Tile `Tasa de esfuerzo` | Dashboard (dentro de la card de deuda, como veredicto) |
| `NetworthEvolutionCard` (evolución del patrimonio) | Dashboard |
| `DebtSummaryCard` (detalle) | `/debt` · en el dashboard queda colapsada a 1 línea |
| `MonthOutlookCard` (runway / resiliencia) | **Dashboard** (decisión firme del usuario) |
| `AccountsSection` | Dashboard (colapsable) |
| Movimientos de deuda por periodo | `/debt` |
| Generador de insight "cargo próximo" (prospectivo) | Se borra (viaja con MonthOutlook) |

| Elemento (hoy en Dashboard) | Destino |
|---|---|
| `StitchKpiRow`, `StitchBalanceChart`, `StitchSecondaryMetrics`, `StitchRecentActivity`, `StitchTipCard` | Duplicados de Análisis → colapsan a la card "Finanzas Domésticas" (5 superficies → 1 línea). **Se borra código** |

## Estado de implementación (2026-07-18)

**Hecho (backend de la métrica — ventana segura de validación, sin tocar UI):**

- **PHASE-43.1 — ventana de recurrencia correcta.** `_recurrence_window` clampa a
  hoy y usa sólo meses naturales completos; añade `recurrence_available` +
  `window_months_with_data` a la respuesta (el fallo silencioso deja de serlo).
  Golden unit determinista (6 casos con `now` inyectable). Corrige el off-by-one
  del borrador (el mes del ancla entra si es su último día → "Año 2025" = jul–dic,
  no jun–nov).
- **PHASE-43.2 backend — override por categoría + explicabilidad.** Enum
  `categories.expense_nature` (`auto`/`structural`/`exceptional`, migración
  aditiva reversible) + cascada de precedencia en `is_structural_expr`
  (**tx > categoría > heurística**) + endpoint `GET
  /analytics/expense-structure/explain` con la `reason` por categoría. Resuelve la
  limitación de la regla 1 a nivel de categoría (§2.5 del plan): un override de
  categoría gana a "un gasto fijo confirmado arrastra toda la categoría".

**Pendiente (el reparto de superficies — el corazón de este ADR):**

- **PHASE-43.2 frontend** — selector `[Automático | Siempre fijo | Siempre
  variable]` en `/settings/categories` + tooltip de razón en el desglose.
- **PHASE-43.3** — Análisis sólo flujos (KPI strip a 2 tiles, card "Top
  movimientos del periodo", aviso de historia insuficiente).
- **PHASE-43.4** — Dashboard sólo stocks (patrimonio + composición + resiliencia +
  cards de módulo por el contrato de agregación).
- **PHASE-43.5** — `/debt` absorbe los movimientos de deuda por periodo.
- **PHASE-43.6** — re-ejecutar el barrido de código muerto tras 43.3/43.4 (la
  poda inicial de 8 componentes ya está hecha).

## Consecuencias

**A favor:**

- **Elimina la duplicación** Dashboard/Análisis por la raíz: cada superficie tiene
  una pregunta, así que una card nueva tiene un sitio evidente y las dos páginas
  dejan de converger.
- **Habilita los verticales futuros sin refactor**: el contrato de agregación
  hace que añadir inversión/bitcoin sea sumar una card, no tocar el dashboard.
- **Menos código**: colapsar 5 superficies duplicadas del dashboard a 1 línea +
  quitar el generador de insight prospectivo borra componentes.
- **Coherente con ADR-0004**: la verdad del dinero vive en la transacción; aquí la
  *presentación* del dinero se reparte por naturaleza (stock vs flujo), no por
  inercia.

**En contra / riesgos:**

- **El dashboard queda "vacío" hasta que existan inversión/BTC**: 2 cards reales
  (finanzas + deuda) + placeholders honestos. Es correcto —mejor eso que duplicar
  Análisis—, pero hay que asumir que la página más cara mostrará poco al principio.
- **`MonthOutlookCard` es una apuesta**: se mueve al dashboard como card de
  resiliencia (decisión firme del usuario, sin periodo de prueba). Si con el
  tiempo no se mira, es candidata a borrar; una métrica que su dueño no reconoce
  no gana sitio en el dashboard.
- **Reparto de zona muy curada** (PHASE-29→37→41): mover superficies puede
  reintroducir regresiones visuales. Mitigación: 43.1–43.2 backend ya validados
  aparte; el frontend se hace por fases con la app funcionando en cada paso.
- **El contrato de agregación es inversión a futuro**: su valor pleno llega con el
  2º vertical. Con uno solo, `personal-finance/dashboard-summary` es casi
  ceremonia. Se acepta porque el coste es bajo y evita rehacer el dashboard cuando
  llegue inversión.

## Alternativas descartadas

- **Dejar Dashboard y Análisis como están** (dos vistas que responden lo mismo):
  es el estado actual; la duplicación crece con cada card y nadie sabe dónde va
  cada cosa.
- **Fusionar Dashboard en Análisis** (una sola página): pierde el lugar natural
  del patrimonio consolidado (que cruza módulos) y no escala cuando haya 4
  verticales — Análisis sería un cajón de sastre.
- **Mover los pagos de deuda a Análisis**: contradice la narrativa de gastos
  (la mitad son movimientos neutros, no gasto) — el mismo error de "qué es un pago
  de deuda" que corrigió la familia PHASE-34/37/38.

## Notas y follow-ups (fuera del alcance de este ADR)

- **Backend — sacar `dashboard` de `personal_finance/`.** Hoy el "agregador" vive
  dentro de un vertical. Con el contrato de agregación, su sitio es
  `backend/app/modules/dashboard/` (transversal). Hoy es barato (un vertical); con
  cuatro deja de serlo. Es el mismo movimiento que el análisis del módulo pide
  para la deuda (split-brain H2). Candidato a **PHASE-44**, no bloquea 43.x.
- **`/debt`: ¿vertical completo o sección de personal-finance?** Esta pregunta
  (abierta desde PHASE-30) es **ortogonal** a este ADR: la decisión "deuda = la
  superficie de detalle del flujo «cómo va mi deuda»" es compatible con ambas.
  Se resuelve aparte.
- **Recalibrar `RECURRENCE_MIN_MONTHS` / banda**: sólo con datos reales post-43.1,
  nunca "para que salgan más fijos" antes de arreglar la ventana.
