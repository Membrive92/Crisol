# PHASE-43 — Reparto Dashboard/Análisis + reparación de la métrica estructural

**Estado**: ✅ implementada (2026-07-18) — pendiente sanity check + UAT del usuario.
43.1 (ventana) · 43.2 (override + explicabilidad, backend + FE) · 43.3 (Análisis
solo flujos) · 43.4 (contrato de agregación + Dashboard solo stocks) · 43.5
(/debt absorbe movimientos) · 43.6 (poda). Verde: FE typecheck+lint+test+knip ·
BE ruff+mypy+pytest. Decisiones tomadas en implementación: veredicto de finanzas
por **signo del flujo de caja** (±5% banda muerta); `DebtSummaryCard` **partida**
en `ModuleCard` (dashboard, 1 línea) + `DebtMovementsCard` (/debt, detalle).
**Estado original**: 📋 planificada
**Rama propuesta**: `feat/phase-43-dashboard-analysis-split`
**Depende de**: ADR-0004 (`flow` como verdad del dinero), PHASE-37 (analytics
estructural), PHASE-41 (simplificación del módulo)
**ADR asociado**: [ADR-0006](../decisions/0006-balance-vs-income-statement.md)
(escrito 2026-07-18; el §1 de abajo fue su borrador)

## Objetivo

Dos objetivos acoplados por la misma decisión de producto:

1. **Reparar la métrica estructural/puntual**, que hoy produce números en los
   que el usuario no puede confiar (§2). Es la prioridad: el KPI de tasa de
   ahorro estructural afirma que la situación real es 6× mejor que la que
   muestra el KPI principal, y esa afirmación no es fiable.
2. **Repartir las superficies** entre Dashboard (stocks: patrimonio, deuda) y
   Análisis (flujos: gastos, ahorro, tendencia), siguiendo la separación
   balance / cuenta de resultados. Hoy ambas páginas responden la misma
   pregunta con componentes distintos.

---

## 1. ADR-0006 — Separación balance / cuenta de resultados

**Contexto**: `/dashboard` y `/personal-finance/analysis` consumen los mismos
hooks (`useDashboardSummary`, `useDashboardByCategory`, `useDashboardByMonth`,
`useAccountBalances`). `/analysis` es un superconjunto estricto: añade
`useDebtHealth`, `useExpenseStructure`, `usePositionHistory`, `useMonthOutlook`,
`usePositionAsOf`. Ambas pintan patrimonio neto, ingresos/gastos del periodo,
breakdown por categoría, evolución mensual y navegador de periodo.

Además, el "módulo global de agregación" vive físicamente en
`backend/app/modules/personal_finance/dashboard/` y sus 7 endpoints son todos
métricas de finanzas domésticas. El comentario del registry
(*"combina ingresos y gastos de TODOS los módulos verticales"*) es una
aspiración, no una descripción.

**Decisión**: cada página responde una pregunta y una sola.

| Página | Pregunta | Naturaleza | Equivalente contable |
|---|---|---|---|
| `/dashboard` | *"¿Cuánto valgo?"* | **Stocks** | Balance |
| `/personal-finance/analysis` | *"¿En qué gasté y cuánto ahorré?"* | **Flujos** | Cuenta de resultados |
| `/debt` | *"¿Cómo va mi deuda?"* | Detalle | Notas |

**Razón de fondo**: `patrimonio neto = activos − pasivos` **cruza módulos**.
Hoy son finanzas + deuda; mañana + inversión + bitcoin + inmuebles. Ningún
vertical puede calcularlo — sólo el agregador. Es la única métrica que
legítimamente *pertenece* al dashboard y la razón por la que debe existir.

**Regla dura para las cards del dashboard**: una card de módulo es
**veredicto + un número + un link**. No un mini-módulo. Si `DebtSummaryCard` se
muda tal cual (esfuerzo + cuota + APR + lista de movimientos), se mueve el
problema en vez de resolverlo. La versión correcta es una línea:

```
💳 Deuda      −19.500 €      esfuerzo 10,3 % · saludable      →
```

El modo de fallo del "dashboard de portfolio" es acabar siendo un muro de todo
que no contesta nada, porque cada módulo quiere su rincón y nadie dice que no.
Esta regla es el "no".

**Consecuencia sobre la definición de ahorro**: al llevarse el patrimonio al
dashboard, `/analysis` pierde `NetworthEvolutionCard`. El ahorro en Análisis es
**flujo del periodo**; el ahorro acumulado (stock) es patrimonio y vive en el
dashboard. Coherente y deliberado.

**Consecuencia estructural**: `backend/app/modules/personal_finance/dashboard/`
debería salir a `backend/app/modules/dashboard/`. Hoy es barato (un vertical);
con cuatro módulos deja de serlo. Se difiere a §6 (no bloquea).

---

## 2. Diagnóstico de la métrica estructural (el bug)

### 2.1. Bug A — La ventana de recurrencia no se clampa a hoy (catastrófico)

`analytics/service.py:78-79`:

```python
window_end = date_to if date_to is not None else datetime.now(UTC)
window_start = _month_floor_shift(window_end, RECURRENCE_WINDOW_MONTHS - 1)
```

`pickYear` (`time-selector.tsx:88`) emite `dateTo = Date.UTC(year, 11, 31, 23, 59, 59)`.

| Periodo seleccionado | Ventana resultante | Meses con datos | Efecto en regla 3 |
|---|---|---|---|
| **Año en curso (2026)**, hoy 17/07 | 01/07/2026 → 31/12/2026 | **1** (julio parcial) | `len(active)=1 < min_months=4` → **ninguna categoría recurre** |
| Año pasado (2025) | 01/07/2025 → 31/12/2025 | 6 | Clasifica **todo 2025** con sólo el 2º semestre |
| Custom 15/05 → 15/06/2026 | 01/01 → **15/06** | 5 completos + junio truncado | Ver bug B |

Con el **año en curso**, `structural_ids` degrada silenciosamente a
`seed` (reglas 1+2: `fixed_expenses` confirmados + rol de deuda). La regla 3 no
aporta nada, `savings_rate_structural` es ruido y el toggle
`[Todo | Fijo | Variable]` marca casi todo como Variable. **Sin ningún aviso.**

### 2.2. Bug B — El mes truncado consume una de las dos holguras

La regla 3 pide `in_band ≥ 4` de una ventana de 6. Cuando `window_end` cae a
mitad de mes, el último bucket contiene ~50 % de un mes normal → queda fuera de
la banda ±40 % (cuyo suelo es el 60 % de la mediana). Aritmética exacta para una
categoría con **exactamente 4 meses** de historia:

```
active = [full, full, full, half]
sorted = [half, f1, f2, f3] → median = (f1+f2)/2 ≈ full
in_band = 3  (half fuera)  →  3 < 4  →  NO recurrente  →  puntual ✗
```

**Cualquier gasto recurrente iniciado hace 4 meses está garantizado mal
clasificado** en cuanto el rango termina a mitad de mes. Candidatos observados en
los datos del usuario (rango 15/05–15/06/2026): "Psicóloga" (65,00 €),
"Inteligencia Artificial" (108,90 €).

La elección de la **mediana** como centro (en vez de la media) fue correcta y
resiste el mes parcial; el problema no es el centro, es que el mes parcial ocupa
un hueco del conteo.

### 2.3. Bug C — El override manual sólo existe a nivel de transacción

`exceptional-toggle.tsx` funciona y está en el detalle de transacción, pero el
usuario quiere declarar *"Supermercado siempre es fijo"* y sólo puede declarar
*"esta compra del 12 de marzo es fija"*. Marcar transacción a transacción no
escala → la métrica nunca converge. Falta el override a nivel de **categoría**.

### 2.4. Bug D — La métrica es una caja negra

No hay forma de ver **por qué** una categoría salió Fija o Variable. Sin
explicabilidad el usuario no puede ni confiar ni corregir: el KPI se ignora.

### 2.5. Limitación conocida (no bug) — Regla 1 es a nivel de categoría

*"Si tienes un `fixed_expense` confirmado en Ocio (Netflix), **todos** los
gastos de Ocio son estructurales"* — incluye el cine y las cañas. Es la
aproximación documentada en PHASE-37.3. **No se cambia en esta fase**: el
override de categoría (§3.3) es la vía de escape correcta y más barata que
llevar la regla 1 a nivel de transacción.

---

## 3. Sub-fases

| Fase | Contenido | Riesgo |
|---|---|---|
| 43.1 | **Backend — ventana de recurrencia correcta** (bugs A y B) | Alto: mueve números del core |
| 43.2 | **Backend — override por categoría + explicabilidad** (bugs C y D) | Medio: migración aditiva |
| 43.3 | **Web — Análisis: sólo flujos** | Medio |
| 43.4 | **Web — Dashboard: sólo stocks** | Medio |
| 43.5 | **Web — Debt absorbe pagos por periodo** | Bajo |
| 43.6 | **Limpieza**: borrar código muerto + componentes huérfanos | Bajo |

**43.1 y 43.2 son backend puro y se pueden mergear sin tocar UI** — la app sigue
funcionando con la vista actual mientras se valida el cálculo. Recomendado
separar temporalmente: es una ventana segura para verificar los números antes de
mover superficies.

---

## PHASE-43.1 — Ventana de recurrencia correcta

### Regla nueva

> La ventana de recurrencia son los **N últimos meses naturales COMPLETOS**
> terminados en `min(date_to, hoy)`. El mes en curso o parcial **se excluye**.

```python
def _recurrence_window(
    date_to: datetime | None, *, now: datetime | None = None
) -> tuple[datetime, datetime]:
    """PHASE-43.1 — ventana de N meses naturales COMPLETOS.

    - Clamp a hoy: un rango que termina en el futuro (p. ej. "Año en curso",
      que emite 31/12) no puede anclar la ventana en meses sin datos.
    - Sólo meses completos: un bucket truncado vale ~50% de un mes normal,
      cae fuera de la banda ±40% y consume un hueco del conteo `in_band`.
    - `now` inyectable → tests deterministas (no dependen del reloj).

    Trade-off aceptado (ya documentado en PHASE-37.3): un gasto recurrente
    nuevo tarda un mes natural en poder clasificarse como estructural.
    """
    now = now if now is not None else datetime.now(UTC)
    anchor = min(date_to, now) if date_to is not None else now
    anchor_date = anchor.date()
    last_day = calendar.monthrange(anchor_date.year, anchor_date.month)[1]
    # OJO (corrección al borrador): NO excluir siempre el mes del ancla. Se
    # excluye SÓLO si el ancla NO es su último día. Si el ancla cae en fin de
    # mes (p. ej. "Año 2025" → 31/12), ese mes está completo y SÍ entra — el
    # borrador original (`_month_floor_shift(anchor, 0) - 1µs` incondicional)
    # daba jun–nov para Año 2025, contradiciendo su propia tabla (jul–dic) y
    # rompiendo el test existente que usa date_to=30/06 (un fin de mes).
    anchor_month_complete = anchor_date.day == last_day
    months_back = 0 if anchor_month_complete else 1
    window_end = _month_floor_shift(anchor, months_back - 1) - timedelta(microseconds=1)
    window_start = _month_floor_shift(window_end, RECURRENCE_WINDOW_MONTHS - 1)
    return window_start, window_end
```

> **Implementado (2026-07-17)** con esta corrección. La tabla de verificación
> de abajo (incl. "Año 2025 → jul–dic") ya reflejaba el comportamiento
> correcto; era el pseudocódigo del borrador el que tenía el off-by-one.
> El golden es un test unit sobre `_recurrence_window` con `now` pinado
> (determinista) que cubre las 6 filas de la tabla, en vez de un golden
> end-to-end dependiente del reloj.

Verificación de la regla contra los casos rotos:

| Caso | Ventana actual (rota) | Ventana nueva |
|---|---|---|
| Año 2026 (hoy 17/07) | 01/07 → 31/12/2026 (1 mes con datos) | **01/01 → 30/06/2026** (6 completos) |
| Año 2025 | 01/07 → 31/12/2025 | **01/07 → 31/12/2025** (igual — correcto para ese año) |
| Custom 15/05 → 15/06/2026 | 01/01 → 15/06 (junio truncado) | **01/12/2025 → 31/05/2026** (6 completos) |
| Mes en curso (julio) | 01/02 → 31/07 (julio parcial) | **01/01 → 30/06** |
| Sin rango (todo el histórico) | 6 meses hasta hoy (mes actual parcial) | **6 completos hasta el mes anterior** |

### Edge cases a cubrir

1. **Usuario nuevo con < 4 meses completos**: `len(active) < min_months` para
   todas → `structural_ids = seed` (reglas 1+2). **No es silencioso**: se
   añade `recurrence_available: bool` + `window_months_with_data: int` a la
   respuesta y la UI lo dice (§43.3). El bug A era exactamente esto sin avisar.
2. **`date_to` en el pasado lejano** (p. ej. Año 2023): ventana = Jul–Dic 2023.
   Correcto — clasifica con el histórico de entonces, no con el actual. Es el
   comportamiento que el docstring original ya pretendía.
3. **`structural_monthly_avg`** usa la misma ventana → deja de estar contaminado
   por meses parciales. Esto **mueve el runway** (`liquid / structural_avg`).
   Golden test obligatorio.

### Archivos

```
backend/app/modules/personal_finance/analytics/service.py   [_recurrence_window nueva; get_expense_structure y get_month_outlook la usan]
backend/app/modules/personal_finance/analytics/schemas.py   [+ recurrence_available, window_months_with_data, window_start, window_end]
backend/tests/test_expense_structure.py                     [casos de la tabla de arriba]
```

### Tests

- **Regresión del bug A**: usuario con 12 meses de datos, `date_to = 31/12` del
  año en curso → `recurring` no vacío (hoy sale vacío). **Este test falla en
  `main`.**
- **Regresión del bug B**: categoría con exactamente 4 meses de historia,
  rango terminando a mitad de mes → clasificada estructural. **Falla en `main`.**
- Año pasado completo → ventana = 2º semestre de ese año (sin cambio).
- Usuario con 2 meses de datos → `recurrence_available = False`,
  `window_months_with_data = 2`, `structural_ids == seed`.
- **Golden**: `structural_monthly_avg` y `runway_months` antes/después con un
  fixture fijo — el cambio de sus valores debe ser explicable, no accidental.

---

## PHASE-43.2 — Override por categoría + explicabilidad

### Migración

> **Implementado (2026-07-18)** — labels en MAYÚSCULAS, no minúsculas como el
> borrador. SQLAlchemy persiste el NOMBRE del miembro del `StrEnum`, no su
> value (verificado: `categorykind` guarda 'EXPENSE', no 'expense'). Con labels
> lowercase, SQLAlchemy escribiría 'AUTO' contra un tipo que sólo tiene 'auto'
> → error en runtime. La API sí serializa el value lowercase vía Pydantic.

```sql
CREATE TYPE expensenature AS ENUM ('AUTO', 'STRUCTURAL', 'EXCEPTIONAL');
ALTER TABLE categories
  ADD COLUMN expense_nature expensenature NOT NULL DEFAULT 'AUTO';
```

Aditiva, reversible, sin backfill (todas las categorías arrancan en `auto` =
comportamiento actual). Migración `f9v25x7us9w8v4`; up/down probados sin pérdida.

### Cascada de precedencia (documentar en el docstring)

```
1. transactions.is_exceptional  (TRUE/FALSE)   ← override por transacción (ya existe)
2. categories.expense_nature    (structural/exceptional) ← override por categoría (NUEVO)
3. heurística                   (reglas 1 ∪ 2 ∪ 3)
```

`is_structural_expr` pasa a:

```python
def is_structural_expr(
    structural_category_ids: set[uuid.UUID],
    *,
    category_alias,          # join a categories para leer expense_nature
) -> ColumnElement[bool]:
    heuristic = (
        Transaction.category_id.in_(list(structural_category_ids))
        if structural_category_ids else literal(False)
    )
    return case(
        # 1. override por transacción
        (Transaction.is_exceptional.is_(True), literal(False)),
        (Transaction.is_exceptional.is_(False), literal(True)),
        # 2. override por categoría
        (category_alias.expense_nature == ExpenseNature.EXCEPTIONAL, literal(False)),
        (category_alias.expense_nature == ExpenseNature.STRUCTURAL, literal(True)),
        # 3. heurística
        else_=heuristic,
    )
```

**Cuidado**: `is_structural_expr` se usa hoy en `expense_split_totals`,
`structural_monthly_avg`, `top_exceptional_transactions` y
`exceptional_by_category`. Las cuatro necesitan el join a `categories`. Auditar
que ninguna lo haga ya con otro alias (colisión).

> **Implementado (2026-07-18)** — auditoría hecha: los 6 joins a `Category` del
> repositorio usan el MODELO `Category` directo, sin `aliased(Category)`. Así
> que NO hizo falta el parámetro `category_alias` del borrador; la expresión
> referencia `Category.expense_nature` directamente. Con `category_id` NULL
> (outerjoin sin match) la columna es NULL, las dos ramas del override de
> categoría dan NULL/False y cae a la heurística — correcto.

### Explicabilidad (bug D)

Endpoint nuevo:

```
GET /analytics/expense-structure/explain?date_from=&date_to=
```

```python
class CategoryStructureExplain(BaseModel):
    category_id: uuid.UUID
    category_name: str
    is_structural: bool
    reason: Literal[
        "override_category",      # expense_nature != auto
        "rule_1_fixed_expense",   # fixed_expense confirmado apunta aquí
        "rule_2_debt_role",       # role DEBT_PAYMENT/DEBT_INTEREST
        "rule_3_recurrence",      # recurre con importe estable
        "not_recurring",          # evaluada y no cumple
        "insufficient_history",   # < min_months activos en ventana
    ]
    months_active: int            # meses con gasto en la ventana
    months_in_band: int           # de esos, cuántos dentro de ±banda
    median_monthly: Decimal | None
    tx_overrides: int             # nº de tx de la categoría con override propio
```

Esto es lo que convierte el KPI de "número que ignoro" en "número que puedo
auditar y corregir". Sin él, el override de categoría es a ciegas.

### UI del override

- **`/settings/categories`**: selector por categoría
  `[Automático | Siempre fijo | Siempre variable]` con hint de qué dice la
  heurística ahora ("automático: variable — 3 de 6 meses en banda").
- **Desglose de gastos**: click en una categoría → tooltip con la razón (del
  endpoint explain) + acceso directo a fijarla.

### Archivos

```
backend/alembic/versions/xxxx_category_expense_nature.py       [nuevo]
backend/app/modules/personal_finance/categories/models.py      [+ expense_nature, enum]
backend/app/modules/personal_finance/categories/schemas.py     [+ expense_nature en Read/Create/Update]
backend/app/modules/personal_finance/analytics/repository.py   [is_structural_expr + join; explain query]
backend/app/modules/personal_finance/analytics/{service,router,schemas}.py [endpoint explain]
apps/web/app/(app)/settings/categories/page.tsx                [selector]
apps/web/components/analysis/stitch-expense-breakdown.tsx      [tooltip de razón]
packages/types/src/models/{category,analytics}.ts
packages/services/src/query/hooks/useExpenseStructureExplain.ts [nuevo]
backend/tests/test_expense_structure.py                        [cascada de precedencia]
backend/tests/test_categories.py                               [expense_nature]
```

### Tests

- Precedencia: tx con `is_exceptional=TRUE` en categoría con
  `expense_nature=structural` → **puntual** (gana la tx).
- Categoría `expense_nature=structural` sin recurrencia → estructural.
- Categoría `expense_nature=exceptional` con `fixed_expense` confirmado →
  **puntual** (el override gana a la regla 1 — resuelve la limitación §2.5).
- `explain` devuelve `reason` correcto para cada una de las 6 razones.
- Migración `up`/`down` reversible; default `auto` ≡ comportamiento pre-fase.

---

## PHASE-43.3 — Web: Análisis sólo flujos

### Qué se queda

| Card | Cambio |
|---|---|
| `StitchIncomeVsExpenses` | Sin cambios |
| `StitchExpenseBreakdown` | + tooltip de razón (43.2) |
| **KPI strip → 2 tiles** | Ver abajo |
| `StitchSmartInsights` | Podar el generador "cargo próximo" (prospectivo → se va con MonthOutlook al dashboard) |

### KPI strip nuevo (de 5 tiles a 2)

Los 5 actuales son 3 conceptos: `Patrimonio` + `Δ patrimonio` = uno (valor y su
delta); `Flujo de caja neto` + `Tasa de ahorro` = uno
(`cashflow = I−G`; `tasa = (I−G)/I` — el mismo hecho en dos unidades).

| # | Tile | Valor | Sub-valor |
|---|---|---|---|
| 1 | **Flujo de caja neto** | `balance` | `tasa de ahorro %` + Δ vs periodo anterior + badge estructural (ya existe) |
| 2 | **Gasto estructural / mes** | `structural_monthly_avg` | *"sin puntuales"* + aviso si `recurrence_available = false` |

Patrimonio, Δ patrimonio y Tasa de esfuerzo **se van al dashboard** (§43.4).

El tile 2 es nuevo y usa un dato **que el backend ya calcula y nadie muestra**
(hoy `structural_monthly_avg` sólo se usa como denominador del runway).
Responde *"¿cuánto cuesta mi vida al mes?"*, que es núcleo del JTBD declarado
(consultar gastos), no una métrica de cockpit.

### Card nueva: "Top movimientos del periodo"

`top_exceptional` **se calcula en el backend y no se muestra** (verificado por
grep). Responde *"¿qué pasó este mes?"* en 5 líneas, más rápido que el donut.
Coste: un `map` sobre datos que ya viajan en la respuesta de
`/analytics/expense-structure`.

### Qué se va de Análisis

| Elemento | Destino |
|---|---|
| Tile `Patrimonio neto` + `Δ patrimonio` | Dashboard |
| Tile `Tasa de esfuerzo` | Dashboard (dentro de la card de deuda, como veredicto) |
| `NetworthEvolutionCard` | Dashboard |
| `DebtSummaryCard` | Dashboard (colapsada a una línea) + `/debt` (el detalle) |
| `MonthOutlookCard` | **Dashboard** (decisión del usuario) |
| `AccountsSection` | Dashboard |
| Generador de insight "cargo próximo" | Se borra (viaja con MonthOutlook) |

### Aviso de historia insuficiente

Si `recurrence_available = false`, el badge estructural y el tile 2 muestran
*"Historia insuficiente ({n}/6 meses) — la clasificación usa sólo tus gastos
fijos confirmados"*. Cierra el fallo silencioso del bug A.

---

## PHASE-43.4 — Web: Dashboard sólo stocks

### Composición nueva

```
┌─ PATRIMONIO ─────────────────────────────────────────────────┐
│  11.370,42 €    Δ +292,45 € (+2,6 %)    ⌁ sparkline          │
│  [Evolución del patrimonio — chart, ex-NetworthEvolutionCard] │
└──────────────────────────────────────────────────────────────┘
┌─ COMPOSICIÓN ────────────┐ ┌─ RESILIENCIA (ex-MonthOutlook) ─┐
│ activos vs pasivos       │ │ Comprometido restante · Runway   │
│ (por módulo cuando haya) │ │ + lista de cargos previstos      │
└──────────────────────────┘ └──────────────────────────────────┘
┌─ MÓDULOS ────────────────────────────────────────────────────┐
│ 🏠 Finanzas Domésticas   +287,86 € este mes · ahorro 9,4 %  →│
│ 💳 Deuda                 −19.500 € · esfuerzo 10,3 % · ok   →│
│ 📈 Inversión             (próximamente)                       │
│ ₿  Bitcoin               (próximamente)                       │
└──────────────────────────────────────────────────────────────┘
┌─ CUENTAS (colapsable, ex-AccountsSection) ───────────────────┐
└──────────────────────────────────────────────────────────────┘
```

### Contrato de agregación (prepara el futuro)

Cada vertical expone:

```
GET /{module}/dashboard-summary
→ { verdict: "healthy"|"caution"|"stressed"|"neutral",
    headline_value: Decimal, headline_label: str,
    secondary: [{label, value}], link: str }
```

El dashboard **compone**, no calcula (salvo el patrimonio consolidado, que es
suyo por definición). Cuando llegue inversión, su card sale sola sin tocar el
dashboard. Es el diseño que el registry ya prometía y que hoy no existe.

**MVP**: implementarlo para `debt` y `personal-finance`. Los verticales futuros
lo implementan al nacer.

### Qué se borra del dashboard actual

`StitchKpiRow`, `StitchBalanceChart`, `StitchSecondaryMetrics`,
`StitchRecentActivity`, `StitchTipCard` son duplicados de Análisis. Colapsan a
la card "Finanzas Domésticas" (5 superficies → 1 línea). **Se borra código.**

---

## PHASE-43.5 — Debt absorbe los pagos por periodo

**Pagos de deuda por periodo va a `/debt`, no al dashboard.** Razón: un pago es
un **flujo**; el dashboard son stocks. Y hay un problema de fondo del propio
ADR-0004:

| Línea | `flow` | ¿Es gasto? |
|---|---|---|
| `CARGO AMORTIZACIÓN PRÉSTAMO` | `OUT` | **Sí** |
| `ADEUDO MENSUAL DE TARJETA` | `TRANSFER_OUT` | **No** (ya contado compra a compra) |
| Cuota de operación financiada | `TRANSFER_OUT` | **No** |

*"Pagos de deuda"* **no es una categoría contable homogénea**: la mitad son
gastos y la otra mitad movimientos neutros. Por eso tampoco puede ir a
`/analysis` (contradiría la narrativa de gastos) ni es un KPI de balance. Es
trazabilidad de deuda → su sitio es `/debt`, junto al cuadro de amortización,
donde la pregunta *"¿cuánto llevo pagado y cuándo?"* tiene sentido.

`components/debt/period-navigator` ya existe y lo importan ambas páginas — la
infraestructura está.

**Contenido de `/debt` tras la fase**: KPIs completos (esfuerzo, cuota, APR,
time-to-payoff) · contratos + cuadros · **movimientos de deuda por periodo**
(ex-`DebtSummaryCard`) · `dashboard-summary` endpoint (43.4).

---

## PHASE-43.6 — Limpieza

Borrar los 5 componentes muertos detectados por barrido de imports
(**2.038 LoC**, ≈10 % de los componentes web):

| Fichero | LoC | Origen |
|---|---|---|
| `components/analysis/position-hero.tsx` | 855 | PHASE-37.2 lo desmontó, no lo borró |
| `components/accounts/balances-card.tsx` | 404 | sustituido por `accounts-section` |
| `components/dashboard/debt-health-card.tsx` | 373 | sustituido por `debt-summary-card` |
| `components/analysis/stitch-key-metrics.tsx` | 333 | sustituido por `kpi-strip` |
| `components/ui/fab.tsx` | 73 | huérfano |

**Peligro concreto**: `position-hero.tsx` contiene una copia del gauge de tasa
de esfuerzo. Si alguien "arregla" un umbral ahí, no arregla nada y no se entera.
El código muerto que *parece* vivo es peor que el obvio.

Más los que 43.3/43.4 dejen huérfanos (`StitchKpiRow`, `StitchBalanceChart`,
`StitchSecondaryMetrics`, `StitchRecentActivity`, `StitchTipCard`,
`kpi-strip` si el strip nuevo no lo reusa). **Re-ejecutar el barrido al cerrar
43.4**, no asumir la lista.

---

## 4. Verificación global

- [ ] `pytest backend/tests/` verde (668 + nuevos).
- [ ] `pnpm typecheck && pnpm lint && pnpm test` verdes (6 paquetes).
- [ ] Migración `up`/`down` reversible; `expense_nature` default `auto` ≡
      comportamiento pre-fase.
- [ ] **Golden**: `expense_structure` y `month_outlook` antes/después de 43.1
      con fixture fijo. Los números **van a cambiar** — cada cambio debe ser
      explicable por la ventana nueva, no accidental.
- [ ] **Smoke manual con datos reales (el que importa)**: seleccionar
      **Año 2026** → `recurring` no vacío, tasa de ahorro estructural creíble.
      Hoy sale degradada a reglas 1+2 sin avisar.
- [ ] Smoke: rango custom 15/05–15/06 → "Psicóloga" e "Inteligencia Artificial"
      clasificadas Fijo (hoy Variable por el bug B).
- [ ] Smoke: marcar una categoría como "Siempre fijo" → se refleja en el KPI y
      en el toggle del desglose al refetch.
- [ ] Smoke: `/analysis` no contiene ninguna métrica de patrimonio ni de deuda.
- [ ] Smoke: `/dashboard` no contiene ningún desglose de gastos por categoría.
- [ ] Barrido de código muerto re-ejecutado tras 43.4.

---

## 5. Riesgos

| Riesgo | Mitigación |
|---|---|
| 43.1 **mueve números del core** (tasa estructural, runway) | Golden tests antes de tocar UI; 43.1-43.2 mergeables sin frontend → ventana de validación |
| El usuario ha calibrado tx a mano bajo la heurística rota | Los overrides de tx **sobreviven** (precedencia 1). Al arreglar la ventana, algunos dejarán de ser necesarios — no se tocan, no molestan |
| `is_structural_expr` + join a `categories` en 4 consumidores | Auditar alias antes de tocar; test por consumidor |
| Dashboard queda vacío hasta que existan inversión/BTC | Es correcto: 2 cards reales + placeholders honestos. Mejor que duplicar Análisis |
| Cambiar `min_months`/`band` "para que salgan más fijos" | **NO**. Primero arreglar la ventana (43.1), luego medir con datos reales, y sólo entonces recalibrar si hace falta — con la lección escrita |

---

## 6. Fuera de alcance (siguiente fase)

- **Mover `dashboard` fuera de `personal_finance`** en el backend (ADR-0006
  §consecuencia estructural). Es el mismo movimiento que H2 pide para deuda.
  Hoy barato, con 4 módulos caro. Candidato a PHASE-44 junto al split-brain de
  deuda.
- **Regla 1 a nivel de transacción** (limitación §2.5) — el override de
  categoría la cubre por ahora.
- **Recalibración de `min_months` / `band`** — sólo con datos post-43.1.
- **`/debt` absorbe `/personal-finance/accounts/[id]/amortization`** (H3 del
  análisis del módulo, PHASE-30 tarea #12) — ortogonal a esta fase.

---

## 7. Decisiones tomadas

- **Dashboard = stocks (balance), Análisis = flujos (resultados), Debt =
  detalle.** Separación con 500 años de historia contable; responde dos
  preguntas que no se mezclan.
- **El patrimonio pertenece al dashboard por construcción**: cruza módulos,
  ningún vertical puede calcularlo.
- **Card de dashboard = veredicto + número + link.** No mini-módulos.
- **Ahorro en Análisis = flujo del periodo**; el acumulado es patrimonio y vive
  en el dashboard.
- **Pagos de deuda por periodo → `/debt`**, no dashboard (son flujos, y no son
  una categoría contable homogénea).
- **`MonthOutlookCard` → dashboard** (decisión del usuario, firme). Se queda en
  el dashboard como card de resiliencia (§43.4). Sin periodo de prueba: es una
  ubicación definitiva, no condicional.
- **La ventana de recurrencia se clampa a hoy y usa sólo meses completos.** El
  trade-off (un recurrente nuevo tarda un mes en registrarse) ya estaba aceptado
  en PHASE-37.3.
- **Override en cascada**: tx > categoría > heurística. El de categoría es el
  que hace la métrica utilizable.
- **Explicabilidad obligatoria**: un KPI que no puedes auditar es un KPI que
  ignoras.
