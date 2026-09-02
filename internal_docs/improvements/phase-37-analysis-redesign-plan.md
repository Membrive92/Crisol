# PHASE-37 — Rediseño módulo Análisis: KPI strip, serie de patrimonio y gasto estructural

**Estado**: 📋 planificada
**Rama propuesta**: `feat/phase-37-analysis-redesign`
**Pre-requisitos**:
- Saldos de cuentas saneados (transferencias bidireccionales +
  `opening_balance` correcto). Si el saldo de la cuenta principal
  sigue siendo incorrecto, los KPIs de esta fase heredan el error.
- Verificar el caso "Intereses YTD = 0,00 € con APR medio > 0 y cuota
  activa" antes de 37.2 — si ninguna transacción cae en las categorías
  de intereses, decidir si es dato ausente real (banco no desglosa) o
  bug de matching, porque la card de deuda del nuevo layout muestra
  ese KPI.

## Contexto

El módulo `/analysis` (PositionHero + cards) tiene tres problemas
observados:

1. **Las cards de patrimonio y salud de deuda no reaccionan al
   selector de periodo**. Causa conceptual: son *stocks* (foto a
   fecha), no *flujos*. La corrección no es filtrarlas por rango sino
   añadirles la dimensión temporal que sí aplica a un stock: la
   **variación en el periodo** (Δ € / Δ %) y su serie histórica. Hoy
   no existe endpoint de serie temporal de patrimonio — solo
   `debt-history` cubre el lado pasivo (gap ya anotado en PHASE-29).
2. **Layout ineficiente**: contenido a ~55% del ancho con laterales
   muertos; el hero (patrimonio + salud + grid de 8 cuentas) consume
   ~40% del viewport vertical antes del primer chart; cuentas a
   jerarquía plana incluyendo saldos 0,00 y "no valorada".
3. **KPIs sin contexto y con redundancia**: ningún KPI muestra Δ vs
   periodo anterior; "Flujo de caja neto" aparece duplicado (card +
   Smart Insight con el mismo dato); "Desglose de gastos" agrupa 22
   categorías en "Otros (39%)", anulando la utilidad del donut; la
   tasa de ahorro mezcla gasto estructural con one-offs (impuestos,
   dentista), produciendo cifras alarmistas que no describen la
   situación estructural real del usuario.

## Decisiones tomadas

- **Los stocks ganan Δ-periodo + sparkline, no filtro por rango.**
  Patrimonio neto = valor actual + variación en el periodo
  seleccionado + serie. La tasa de esfuerzo, al ser un flujo
  (cuotas del periodo / ingresos del periodo), **sí** reacciona al
  selector.
- **Clasificación recurrente/excepcional: heurística automática con
  override manual.** Por defecto, una transacción es *recurrente* si
  matchea un `fixed_expense` confirmado o pertenece a una categoría
  de cadencia detectada; el resto es puntual. El usuario puede
  corregir con un flag manual por transacción
  (`is_exceptional: bool | null` — null = heurística decide, true/false
  = override). Se descarta la clasificación 100 % manual por coste de
  disciplina, y la 100 % automática por falsos positivos sin salida.
- **Smart Insights con criterio de no-redundancia**: un insight solo
  se emite si aporta información no visible ya en un KPI del layout.
  Se elimina el insight "tu saldo neto bajó X €" (duplica el KPI de
  flujo).
- **Grid de 12 columnas a ancho completo** (`max-width` 1520px),
  cuentas colapsadas por defecto.
- **`position_history` generaliza `debt_history`**, no lo duplica.
  El endpoint de deuda queda como vista filtrada del nuevo.

## Sub-fases

| Fase | Nombre | Tipo | Esfuerzo |
|------|--------|------|----------|
| 37.1 | Backend: endpoint `position-history` + Δ-periodo en KPIs | Backend | M |
| 37.2 | Web: KPI strip + grid 12 col + cuentas colapsables | Frontend | M |
| 37.3 | Backend+Web: gasto estructural vs puntual + tasa de ahorro dual | Full-stack | M |
| 37.4 | Backend+Web: proyección fin de mes + runway | Full-stack | S |
| 37.5 | Smart Insights v2: reglas de no-redundancia + insights derivados | Backend | S |
| 37.6 | Mobile parity | Mobile | M (aplazable) |

37.1 → 37.2 son el MVP (resuelven la queja literal: cards estáticas y
espacio desaprovechado). 37.3 → 37.5 son el salto de valor analítico.

---

## PHASE-37.1 — Serie temporal de patrimonio + Δ-periodo

### Endpoint nuevo

```
GET /accounts/position-history?months_back=12&months_forward=0
```

Generaliza el patrón de `debt_history` al patrimonio completo.

**Response** (`accounts/schemas.py`):

```python
class PositionPoint(BaseModel):
    month: date                      # primer día del mes
    total_assets: Decimal
    total_liabilities: Decimal       # ya con signo positivo (deuda)
    net_worth: Decimal               # assets - liabilities
    is_projection: bool = False

class PositionHistoryResponse(BaseModel):
    reference_currency: str
    points: list[PositionPoint]
    delta_period: Decimal | None     # net_worth actual - net_worth inicio del rango pedido
    delta_period_pct: float | None
```

**Implementación** (`accounts/position_history.py`, módulo nuevo):

- Reutilizar la técnica de `debt_history._compute_historical_points`:
  cumulative SQL por mes con el `CASE` de signo existente, pero
  **sin filtrar por `nature=LIABILITY`** — dos series (assets,
  liabilities) en una sola query con `GROUP BY nature, month`.
- Excluir cuentas `is_archived` y tipos no valorados
  (`BROKERAGE`, `CRYPTO`) del cómputo, coherente con la exclusión de
  esos tipos del patrimonio agregado.
- Las transacciones sin categoría siguen la misma regla que el saldo
  actual (si el `else_` del CASE se cambió a 0 en fases previas,
  heredarlo; verificar coherencia entre `get_balances_for_user` y esta
  query — **misma expresión de signo, un solo lugar**: extraer el
  `CASE` a una función compartida `signed_amount_expr()` en
  `accounts/repository.py` para que ambos endpoints no diverjan).
- Proyección (`months_forward > 0`): reutilizar la proyección de
  cuotas teóricas de `debt_history` para liabilities; para assets no
  proyectar (devolver solo histórico) — proyectar ingresos/gastos
  futuros sin modelo es inventar datos.

### Δ-periodo en KPIs existentes

`GET /dashboard/summary` (o el endpoint que alimente el hero — ajustar
al real) gana campos:

```python
net_worth_delta: Decimal | None        # vs inicio del periodo seleccionado
net_worth_delta_pct: float | None
cashflow_delta: Decimal | None         # vs periodo anterior equivalente
savings_rate_delta_pp: float | None    # puntos porcentuales
effort_ratio_delta_pp: float | None
```

Regla de comparación: **periodo anterior equivalente** (mes vs mes
anterior, YTD vs mismo rango del año anterior, custom vs rango
inmediatamente precedente de igual longitud). Documentar en el
docstring — es la convención para todos los Δ de la app.

### Tests (`backend/tests/test_position_history.py`)

- Usuario con 1 asset y 1 liability, 6 meses de tx: 12 puntos, los 6
  primeros con net_worth = opening_balances, serie coherente con los
  saldos actuales en el punto final (**invariante crítico**: el último
  punto histórico == `get_balances_for_user` del momento; test que
  compara ambos endpoints).
- Cuenta brokerage con movimientos: no altera la serie.
- Cuenta archivada a mitad de rango: sus tx anteriores al archivo
  cuentan; verificar comportamiento definido y documentado (decisión:
  archivar excluye la cuenta de toda la serie, para que la serie sea
  reconstruible — anotar en docstring).
- `delta_period` con rango sin datos previos: None, no 0.
- Divisas: solo cuentas en `reference_currency` (misma limitación que
  balances actual; anotar en limitaciones).

---

## PHASE-37.2 — KPI strip + grid 12 columnas + cuentas colapsables

### Estructura nueva de `/analysis` (o `(app)/personal-finance` según ruta real)

```
┌─ KPI STRIP ── height ~92px ── grid-cols-5 ────────────────────────────────┐
│ PATRIMONIO NETO   Δ PERIODO      TASA ESFUERZO    FLUJO NETO   T. AHORRO  │
│ -6.842 €          -3.483 € ▼     10.3 % ●         -3.483 € ▼   -22 % ▼    │
│ ⌁ sparkline 12m   vs per. ant.   BdE <35%         vs per. ant. vs per.ant.│
└────────────────────────────────────────────────────────────────────────────┘
┌─ Ingresos vs Gastos ──────── col-span-8 ─┐ ┌─ Evolución patrimonio (4) ──┐
│ (chart existente, sin cambios)           │ │ AreaChart 12m net_worth      │
│                                          │ │ + líneas assets/liabilities  │
└──────────────────────────────────────────┘ └──────────────────────────────┘
┌─ Desglose de gastos ──────── col-span-6 ─┐ ┌─ Deuda (resumen) (6) ───────┐
│ donut top-6 + fila "Otros (n)" clicable  │ │ cuota mes · esfuerzo ·      │
│ → expande lista completa inline          │ │ próximos vencimientos       │
└──────────────────────────────────────────┘ └──────────────────────────────┘
┌─ Flujo neto mensual ──────── col-span-6 ─┐ ┌─ Smart Insights (6) ────────┐
│ (sparkline existente, promocionada)      │ │ (v2 en 37.5; mientras,      │
└──────────────────────────────────────────┘ │  ocultar los redundantes)   │
                                             └──────────────────────────────┘
┌─ Cuentas ── <details> colapsado por defecto ──────────────────────────────┐
│ ▸ 8 cuentas · 3 deuda · 1 no valorada · patrimonio -6.842 €               │
│   [expandido]: grid actual, ordenado por |saldo| desc, saldos 0 al final  │
│   con opacidad reducida, badge NO VALORADA/DEUDA como hoy                 │
└────────────────────────────────────────────────────────────────────────────┘
```

### Componentes

**Nuevo** `apps/web/components/analysis/kpi-strip.tsx`:
- 5 tiles. Props: `{ label, value, delta?, deltaUnit?, sparkline?, status? }`.
- Δ coloreado (`success`/`danger`) con flecha; para KPIs donde "bajar
  es bueno" (esfuerzo, gasto), invertir el mapeo color-signo vía prop
  `invertDeltaColor`.
- Sparkline solo en Patrimonio (datos de `position-history`); tiles
  sin sparkline mantienen la misma altura (placeholder invisible) para
  alineación.
- Tabular-nums, tokens existentes, sin sombras — coherente con
  DESIGN.md.
- Responsive: `grid-cols-5` ≥1100px → `grid-cols-2` + strip scrollable
  horizontal en móvil web (<640px).

**Nuevo** `apps/web/components/analysis/networth-evolution-card.tsx`:
- AreaChart (Recharts) con `net_worth` como área y
  `total_assets`/`total_liabilities` como líneas secundarias
  toggleables por leyenda.
- Consume `usePositionHistory(12)`.

**Modificado** `apps/web/components/analysis/position-hero.tsx`:
- Se desmonta como hero. El gauge de esfuerzo, la barra de rango de
  patrimonio y el grid de cuentas migran: gauge → tile del strip
  (versión compacta) y card Deuda; grid de cuentas → sección
  colapsable inferior. Mantener el componente durante la transición
  con un flag si se quiere despliegue gradual; si no, sustitución
  directa (recomendado — es una app de un solo despliegue).

**Modificado** `apps/web/components/dashboard/expense-breakdown*.tsx`
(nombre real a confirmar):
- Donut pasa a top-6 + "Otros (n)". La fila "Otros" es un
  `<button>` que expande la lista completa inline (sin modal), con
  las n categorías restantes ordenadas por importe.
- Fix del donut: segmentos separados 2px `surface` (patrón
  PositionHero).

**Layout raíz** de la página:
- `max-width: 1520px; margin-inline: auto;` con grid de 12 columnas
  (`gap: var(--space-lg)`).
- Breakpoints: ≥1100px grid completo; 640-1099px todo a col-span-12
  apilado; <640px paddings `md`.

**Fix de formateo**: normalizar `-0,00 €` → `0,00 €` en el formatter
monetario compartido (`packages/services` o util del web — localizar
`formatCurrency` y aplicar `Object.is(value, -0) || round(value)===0`).

### Tests web

- `kpi-strip.test.tsx`: renderiza 5 tiles; Δ positivo/negativo mapea
  color según `invertDeltaColor`; sin `delta` no renderiza flecha.
- `networth-evolution-card.test.tsx`: con 12 puntos renderiza; con
  serie vacía muestra empty state, no crashea.
- Page test: cuentas colapsadas por defecto; expandir muestra las 8;
  orden por |saldo| desc; cuentas a 0 al final.
- Formatter: `-0.004` → `"0,00 €"`.

---

## PHASE-37.3 — Gasto estructural vs puntual + tasa de ahorro dual

### Modelo de datos

Migración: `transactions.is_exceptional BOOLEAN NULL DEFAULT NULL`.

Semántica de tres estados:
- `NULL` → decide la heurística.
- `TRUE` → el usuario lo marcó como puntual (override).
- `FALSE` → el usuario lo marcó como estructural (override).

### Heurística (backend, `analytics/recurrence.py` o módulo equivalente)

Una transacción EXPENSE es **estructural** si cumple cualquiera:
1. Matchea un `fixed_expense` con `status='confirmed'` (por
   merchant/regla del detector existente).
2. Su categoría tiene rol de deuda (pagos de cuota son estructurales
   por definición).
3. Su categoría aparece en ≥ N de los últimos M meses con importe
   dentro de banda (parámetros iniciales: N=4, M=6, banda ±40 %;
   constantes nombradas, ajustables). Cubre recurrentes sin
   `fixed_expense` (supermercado, gasolina).

Todo lo demás es **puntual**. El override manual (`is_exceptional`)
gana siempre.

**Nota de honestidad sobre la heurística**: la regla 3 clasificará mal
algunos casos (un gasto grande en una categoría habitualmente pequeña
cuenta como estructural si la banda es laxa; el primer mes de un gasto
nuevo recurrente cuenta como puntual). Es el trade-off aceptado; el
override existe para eso. Registrar en `lessons.md` tras 1-2 meses de
uso real si los parámetros N/M/banda necesitan ajuste.

### Endpoint

```
GET /analytics/expense-structure?range=...
```

```python
class ExpenseStructureResponse(BaseModel):
    structural_total: Decimal
    exceptional_total: Decimal
    structural_monthly_avg: Decimal          # base para runway (37.4)
    savings_rate_gross: float | None         # (ingresos - gasto total) / ingresos
    savings_rate_structural: float | None    # (ingresos - gasto estructural) / ingresos
    top_exceptional: list[TxRef]             # 5 mayores puntuales del rango
    exceptional_by_category: list[CategoryAmount]
```

### UI

- Card "Desglose de gastos" gana un segmented control
  `[Todo | Estructural | Puntual]` que filtra donut y lista.
- Tile "T. AHORRO" del strip muestra la bruta; tooltip/expansión
  muestra la estructural con explicación: *"Excluyendo gastos
  puntuales (impuestos, one-offs): +9 %"*. Si difieren en >10pp,
  badge sutil que invita a expandir.
- En detalle de transacción: toggle "Gasto puntual" (tri-estado
  visual: automático / puntual / estructural).

### Tests

- Heurística: cuota de préstamo → estructural; tx que matchea
  fixed_expense → estructural; categoría en 5/6 meses banda ±40 % →
  estructural; gasto único grande → puntual; override TRUE gana a
  cualquier heurística.
- `savings_rate_structural` con ingresos 0 → None.
- Transferencias (`is_transfer`) excluidas de ambos totales.

---

## PHASE-37.4 — Proyección fin de mes + runway

### Endpoint

```
GET /analytics/month-outlook
```

```python
class MonthOutlookResponse(BaseModel):
    committed_remaining: Decimal      # fijos+cuotas confirmados aún no cargados este mes
    committed_items: list[CommittedItem]  # {name, amount, expected_date}
    days_remaining: int
    liquid_balance: Decimal           # Σ cuentas bank+savings+cash no archivadas
    runway_months: float | None       # liquid_balance / structural_monthly_avg (37.3)
```

`committed_remaining`: `fixed_expenses` confirmados con día de cargo
estimado > hoy dentro del mes + `liability_installments` con
`due_date` en lo que queda de mes y no marcadas pagadas.

### UI

- Card compacta en la fila de Deuda o bajo el strip:
  *"Comprometido restante este mes: 890 € (3 cargos) · Colchón: 4,2
  meses de gasto estructural"*.
- Lista expandible de los cargos previstos con fecha.
- `runway_months` con semáforo orientativo (constantes: <3 danger,
  3-6 warning, >6 success — umbrales de la literatura de fondo de
  emergencia; anotar que son orientativos, no normativa).

### Tests

- Cuota con due_date pasado y no pagada: cuenta como comprometida
  (atrasada), flag `overdue`.
- runway con `structural_monthly_avg=0` → None.
- Cuentas brokerage/crypto excluidas de `liquid_balance`.

---

## PHASE-37.5 — Smart Insights v2

### Regla de no-redundancia

Un insight se descarta si su dato principal ya es visible en el strip
o en una card del layout. Implementación: cada generador de insight
declara `surfaces: set[str]` (KPIs que ya muestran ese dato); el
orquestador filtra.

### Insights nuevos (generadores, orden de prioridad)

1. **Concentración de gasto**: si una categoría > 20 % del gasto del
   periodo Y > 2× su media histórica de 6 meses → *"Dentista concentra
   el 20 % del gasto (3.860 €), muy por encima de tu media"*.
2. **Impacto de puntuales**: si `savings_rate_gross < 0` pero
   `savings_rate_structural > 0` → *"Sin los gastos puntuales del
   periodo (X €), tu tasa de ahorro sería +Y %"*. Depende de 37.3.
3. **Deriva de recurrente**: fixed_expense cuyo último cargo > 15 %
   sobre su media → *"Tu recibo de la luz subió un 18 % este mes"*.
4. **Cargo próximo relevante**: mayor `committed_item` de los
   próximos 7 días si > 10 % del ingreso mensual medio. Depende de
   37.4.
5. Se elimina: "tu saldo neto bajó X €" (redundante con strip).

Máximo 3 insights simultáneos, ordenados por prioridad. Sin datos
suficientes → card muestra el estado "detección automática activa"
actual, no insights vacíos.

### Tests

- Generador 1 dispara con el fixture de la captura (Dentista 20 %,
  sin histórico → no dispara por falta de media; con histórico bajo →
  dispara).
- Filtro de redundancia: un insight cuyo `surfaces` interseca con los
  KPIs del strip no se emite.
- Máximo 3.

---

## Archivos clave (consolidado)

### Backend
```
backend/alembic/versions/xxxx_tx_is_exceptional.py                     [37.3]
backend/app/modules/personal_finance/accounts/position_history.py      [nuevo, 37.1]
backend/app/modules/personal_finance/accounts/repository.py            [37.1: signed_amount_expr() compartida]
backend/app/modules/personal_finance/accounts/{router,schemas}.py      [37.1]
backend/app/modules/personal_finance/analytics/recurrence.py           [nuevo, 37.3]
backend/app/modules/personal_finance/analytics/{router,service,schemas}.py [37.3, 37.4]
backend/app/modules/personal_finance/insights/*                        [37.5 — módulo real según repo]
backend/tests/test_position_history.py                                 [nuevo]
backend/tests/test_expense_structure.py                                [nuevo]
backend/tests/test_month_outlook.py                                    [nuevo]
backend/tests/test_insights_v2.py                                      [nuevo]
```

### Frontend shared
```
packages/types/src/models/{position,analytics}.ts                      [nuevos]
packages/services/src/api/endpoints/{accounts,analytics}.ts
packages/services/src/query/hooks/usePositionHistory.ts                [nuevo]
packages/services/src/query/hooks/useExpenseStructure.ts               [nuevo]
packages/services/src/query/hooks/useMonthOutlook.ts                   [nuevo]
packages/services/src/query/keys.ts
```

### Frontend web
```
apps/web/components/analysis/kpi-strip.tsx                             [nuevo]
apps/web/components/analysis/networth-evolution-card.tsx               [nuevo]
apps/web/components/analysis/month-outlook-card.tsx                    [nuevo, 37.4]
apps/web/components/analysis/position-hero.tsx                         [desmontaje]
apps/web/components/dashboard/expense-breakdown*.tsx                   [top-6 + Otros expandible + filtro estructural]
apps/web/app/(app)/.../analysis page                                   [grid 12 col, max-w 1520]
formatter monetario compartido                                          [fix -0,00]
```

## Endpoints añadidos

- `GET /accounts/position-history` (37.1)
- `GET /analytics/expense-structure` (37.3)
- `GET /analytics/month-outlook` (37.4)

## Migraciones

- `transactions.is_exceptional BOOLEAN NULL` (37.3). Reversible sin
  pérdida (drop column).

## Verificación global

- [ ] Invariante: último punto de `position-history` == balances
      actuales (test cruzado entre endpoints).
- [ ] `pytest backend/tests/` verde.
- [ ] `pnpm typecheck && pnpm lint && pnpm test` verdes.
- [ ] Smoke: selector de periodo cambia Δ de todos los tiles del strip
      y la tasa de esfuerzo; el valor absoluto de patrimonio no cambia
      (es un stock) pero su Δ y sparkline sí.
- [ ] Smoke: "Otros (n)" expande la lista completa.
- [ ] Smoke: marcar una tx como puntual recalcula
      `savings_rate_structural` al refetch.
- [ ] Smoke: cuentas colapsadas por defecto; badge NO VALORADA visible
      al expandir.
- [ ] Verificar en un viewport 2560px que el layout usa el ancho hasta
      1520px sin laterales desproporcionados.

## Limitaciones conocidas tras PHASE-37

- `position-history` solo cuenta cuentas en la divisa de referencia
  (misma limitación que balances). Multi-divisa histórica requiere
  tipos de cambio por fecha — fuera de scope.
- La proyección de la serie de patrimonio solo cubre el lado deuda
  (cuotas teóricas). No se proyectan ingresos/gastos futuros.
- La heurística estructural/puntual tendrá falsos positivos el primer
  mes de cualquier gasto recurrente nuevo. Mitigado por override.
- Insights v2 requiere ≥3-6 meses de histórico para los generadores
  basados en media; usuarios nuevos verán pocos insights.
- Mobile mantiene el layout antiguo hasta 37.6.

## Próxima fase

Candidatos: 37.6 (mobile parity) o retomar PHASE-30 (rediseño módulo
deuda en dos capas) si aún no se ha ejecutado — la card "Deuda
(resumen)" de este layout está pensada para enlazar con la Capa 1 de
ese rediseño.
