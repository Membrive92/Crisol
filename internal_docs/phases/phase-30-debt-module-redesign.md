# PHASE-30 — Rediseño módulo deuda: arquitectura en dos capas

**Estado**: 📋 planificada
**Rama propuesta**: `feat/phase-30-debt-redesign`
**ADR asociado**: [ADR-0003](../decisions/0003-debt-module-two-layer-architecture.md)
**Pre-requisito**: [PHASE-31](phase-31-account-integrity.md) (saneamiento de
cuentas) debe estar mergeada antes de esta fase, porque PHASE-30 construye
encima del modelo de cuentas saneado y consume KPIs de flujo que dependen
de la categorización correcta de transferencias.

## Objetivo

Reorientar el módulo `/debt` para que aporte valor **sin requerir
onboarding** (rellenar TIN/plazo/fecha para crear liability accounts).
La fuente de verdad principal pasa a ser el **flujo derivado de
categorías marcadas como deuda**; las liability accounts existentes se
conservan como capa de enriquecimiento opcional ("Detalle por
contrato"). Detalles arquitectónicos en ADR-0003.

Adicionalmente la fase resuelve cinco hallazgos del análisis de
PHASE-22+:

1. **Calibración del DTI a EEUU**. Sustituir bandas 36%/43% por las
   30%/35% del Banco de España y renombrar a "Tasa de esfuerzo".
2. **DTI excluye gastos esenciales**. Añadir variante ampliada
   (deuda + fixed_expenses confirmados) con toggle UI.
3. **`INTEREST_CATEGORY_NAMES` acoplado a strings**. Sustituir por enum
   `categories.role` con migración del `is_transfer` actual.
4. **`time_to_payoff` lineal en hipotecas francesas tempranas**. Usar
   el cuadro francés directo cuando hay schedule.
5. **Cuadro francés con 360 filas**. Condensar a vista anual + expandir
   al mes.

## Sub-fases

| Fase | Nombre | Tipo |
|------|--------|------|
| 30.1 | Migración `categories.role` enum + seed update + tests | Backend infra |
| 30.2 | Endpoint `category-summary` + KPIs Capa 1 + fix `time_to_payoff` | Backend |
| 30.3 | Web — rediseño `/debt` Capa 1 + nueva nav, redirect amortization | Frontend web |
| 30.4 | Web — Capa 2 condensada (cuadro anual/mensual) + nota UX vinculación | Frontend web |
| 30.5 | Mobile parity (opcional, puede diferirse) | Frontend mobile |

Cada sub-fase es entregable independiente. 30.1-30.4 son el MVP del
redesign; 30.5 se evalúa al cerrar 30.4.

---

## PHASE-30.1 — Migración `categories.role` + seed

### Backend

**Migración Alembic** (`m0a14e6097c3d_category_role.py`):

```sql
-- 1. Crear enum
CREATE TYPE categoryrole AS ENUM (
  'GENERIC',         -- categoría normal
  'TRANSFER',        -- transferencia interna (sustituye is_transfer)
  'DEBT_PAYMENT',    -- pago de cuota (capital + intereses mezclados)
  'DEBT_INTEREST'    -- intereses puros + comisiones financieras
);

-- 2. Añadir columna NULLABLE inicialmente para backfill
ALTER TABLE categories ADD COLUMN role categoryrole;

-- 3. Backfill desde is_transfer y nombres conocidos
UPDATE categories SET role = 'TRANSFER' WHERE is_transfer = TRUE;
UPDATE categories SET role = 'DEBT_INTEREST'
  WHERE name IN ('Intereses hipoteca', 'Intereses préstamo', 'Intereses tarjeta')
    AND role IS NULL;
UPDATE categories SET role = 'DEBT_PAYMENT'
  WHERE name IN ('Préstamos e hipotecas', 'Tarjeta de crédito')
    AND role IS NULL;
UPDATE categories SET role = 'GENERIC' WHERE role IS NULL;

-- 4. NOT NULL constraint
ALTER TABLE categories ALTER COLUMN role SET NOT NULL;
ALTER TABLE categories ALTER COLUMN role SET DEFAULT 'GENERIC';

-- 5. Índice parcial para queries de "todas las categorías de deuda"
CREATE INDEX ix_categories_role_debt ON categories(user_id, role)
  WHERE role IN ('DEBT_PAYMENT', 'DEBT_INTEREST');
```

**Política sobre `is_transfer`**: se mantiene la columna durante 30.1
(deprecada) y se elimina en una fase posterior una vez todos los
callers consumen `role`. Permite rollback seguro.

**Archivos backend**:

- `backend/app/modules/personal_finance/categories/models.py` — añadir
  `role: Mapped[CategoryRole] = mapped_column(...)`, enum
  `CategoryRole(StrEnum)`.
- `backend/app/modules/personal_finance/categories/schemas.py` —
  exponer `role` en `CategoryRead`. `CategoryCreate`/`CategoryUpdate`
  aceptan `role` opcional (default GENERIC en service).
- `backend/app/modules/personal_finance/seed/dataset.py` — añadir
  `"role": CategoryRole.DEBT_PAYMENT` / `DEBT_INTEREST` a las 5
  categorías relevantes (Préstamos e hipotecas, Tarjeta de crédito,
  Intereses hipoteca, Intereses préstamo, Intereses tarjeta) +
  `TRANSFER` a las transferencias internas existentes.
- `backend/app/modules/personal_finance/accounts/debt_health.py` —
  reemplazar `INTEREST_CATEGORY_NAMES = frozenset(...)` por
  `Category.role == CategoryRole.DEBT_INTEREST`.
- `backend/app/modules/personal_finance/accounts/debt_history.py` —
  mismo reemplazo.
- `backend/app/modules/personal_finance/transactions/repository.py` —
  donde se filtra `Category.is_transfer == True`, alternativa con
  `Category.role == CategoryRole.TRANSFER` (compat con la columna
  vieja). Sin breaking change.

**Tests** (`backend/tests/test_categories.py` + `test_debt.py`):

- Migración aplicada sin pérdida: una categoría con `is_transfer=True`
  tras migrar tiene `role=TRANSFER`.
- Seed asigna roles correctos en usuario nuevo.
- `interest_paid_ytd` sigue funcionando tras el reemplazo, idéntico
  resultado al test anterior.
- Renombrar "Intereses hipoteca" → "Hipoteca - intereses" no cambia el
  KPI (regresión del bug del frozenset).
- Crear categoría custom con `role=DEBT_INTEREST` la incluye en
  `interest_paid_ytd`.

### Frontend shared

- `packages/types/src/models/category.ts` — añadir `CategoryRole` y
  `Category.role`.
- `packages/services/src/api/endpoints/categories.ts` — el endpoint
  ya devuelve el campo nuevo automáticamente.

### Verificación

- `pytest backend/tests/ -k category` verde.
- `alembic upgrade head` + `alembic downgrade -1` reversibles.
- `pnpm typecheck` verde en packages/types.

### Limitaciones conocidas tras 30.1

- La UI todavía no expone `role` en el form de categorías. Los usuarios
  con categorías custom de deuda tendrán que esperar a 30.3 (o
  marcarlas vía API). Aceptable porque el 100% de las categorías de
  deuda relevantes vienen del seed.

---

## PHASE-30.2 — Backend Capa 1: `category-summary` + KPIs nuevos

### Endpoints nuevos

```
GET /debt/category-summary?range=ytd|12m|month
```

**Response schema** (`backend/app/modules/personal_finance/debt/schemas.py` — módulo nuevo):

```python
class DebtCategorySummary(BaseModel):
    reference_currency: str
    range: Literal["ytd", "12m", "month"]
    range_start: date
    range_end: date

    # Pagos a deuda agregados
    total_payments: Decimal           # Σ flujo categorías DEBT_PAYMENT + DEBT_INTEREST
    interests_and_fees: Decimal       # solo DEBT_INTEREST
    capital_amortized: Decimal        # total_payments - interests_and_fees

    # Composición por tipo (derivada del nombre de la categoría o sub-role)
    by_type: list[DebtTypeBreakdown]  # {type: 'mortgage'|'loan'|'card'|'other', amount, percent}

    # Evolución mensual (siempre 12 puntos cuando range=12m, NaNs al inicio si user reciente)
    monthly_series: list[MonthlyDebtPoint]  # {month, payments, interests, capital}

    # Tasa de esfuerzo
    monthly_income_avg: Decimal
    effort_ratio_strict: float | None         # only debt payments / income
    effort_ratio_strict_status: EffortStatus  # healthy | caution | stressed | unknown
    effort_ratio_extended: float | None       # (debt + fixed_expenses_confirmed) / income
    effort_ratio_extended_status: EffortStatus

    # Cuotas recurrentes detectadas (cross-link a fixed_expenses)
    recurring_quotas: list[RecurringQuotaRef]  # {fixed_expense_id, merchant, amount, category_name}
```

```
GET /debt/health  (alias retro-compatible de /accounts/debt-health)
```

Mantenido. Se anota como **legacy** en `internal_docs/api/endpoints.md`
— a deprecar en PHASE-31. La UI deja de consumirlo en 30.3.

### Cambios en `debt_health.py`

- **Bandas de tasa de esfuerzo** (rename y recalibración):
  ```python
  EFFORT_BAND_HEALTHY = Decimal("0.30")  # Banco España
  EFFORT_BAND_CAUTION = Decimal("0.35")
  # healthy < 0.30, caution [0.30, 0.35], stressed > 0.35

  def _classify_effort(ratio: float | None) -> str:
      if ratio is None: return "unknown"
      if ratio < float(EFFORT_BAND_HEALTHY): return "healthy"
      if ratio <= float(EFFORT_BAND_CAUTION): return "caution"
      return "stressed"
  ```
- **`time_to_payoff`**: cuando un liability tiene schedule, no usar la
  proyección lineal. Sumar las `remaining_balance` filas del cuadro y
  devolver `term_months - meses_transcurridos_desde_start_date`. Solo
  fallback a proyección lineal si no hay schedule (caso tarjetas).
- **Documentar `monthly_income_avg`** en docstring: trabaja sobre el
  flujo de la categoría INCOME que ya viene neto (lo que la cuenta
  recibe). Etiqueta en UI: "ingresos netos".

### Cálculo de "effort_ratio_extended"

Numerador: `monthly_debt_payment` (del flujo Capa 1, no cuotas
teóricas) **+** suma de cuotas mensuales de `fixed_expenses` activos
(`status='confirmed'`, `cadence_days ∈ {30, 28-31}`).

Edge case: si un `fixed_expense` está vinculado a una `category` con
`role IN (DEBT_PAYMENT, DEBT_INTEREST)`, **no se suma dos veces** —
descontar.

### Archivos backend

- `backend/app/modules/personal_finance/debt/__init__.py` — módulo nuevo.
- `backend/app/modules/personal_finance/debt/router.py` — `GET /debt/category-summary`.
- `backend/app/modules/personal_finance/debt/service.py` — orquesta
  las queries.
- `backend/app/modules/personal_finance/debt/repository.py` — queries
  agregadas (Σ amount por mes, filtro por role).
- `backend/app/modules/personal_finance/debt/schemas.py` — Pydantic v2.
- `backend/app/modules/personal_finance/accounts/debt_health.py` —
  ajuste de bandas + fix `time_to_payoff`. Mantener endpoint vivo
  durante 30.x.
- `backend/app/main.py` — registrar el router nuevo.

### Tests (`backend/tests/test_debt_category_summary.py`)

- Usuario sin liability accounts pero con 6 meses de cuotas
  categorizadas: devuelve `effort_ratio_strict` correcto, sin
  weighted_apr.
- Usuario con liability con schedule + cuotas categorizadas: ambas
  capas devuelven datos coherentes, sin doble cómputo.
- `effort_ratio_extended` con un `fixed_expense` vinculado a categoría
  de deuda: no suma doble.
- `monthly_series` con un usuario que entró hace 3 meses: 12 puntos
  con los 9 iniciales en 0.
- `time_to_payoff` para una hipoteca con 60 meses transcurridos de 240:
  devuelve 180, no la proyección lineal (test que falla en main hoy).
- Bandas correctas: ratio 0.32 → "caution", ratio 0.40 → "stressed",
  ratio 0.28 → "healthy".

---

## PHASE-30.3 — Web: rediseño `/debt` Capa 1

### Nueva jerarquía de la página `/debt`

Ver wireframe en
[`internal_docs/design-explorations/debt-redesign-30/wireframe.md`](../design-explorations/debt-redesign-30/wireframe.md).
Resumen:

```
┌─────────────────────────────────────────────────────────────┐
│ DEUDA · Salud · {effort_status}                             │
├─────────────────────────────────────────────────────────────┤
│ ① Tasa de esfuerzo  [toggle: Estricta | Ampliada]           │
│    {value}%  ─────●────────────────────                     │
│    [0%]    [30%]    [35%]    [50%]                          │
│    "X € de tus Y € netos mensuales van a deuda"             │
├─────────────────────────────────────────────────────────────┤
│ ② Pagos a deuda este año (range selector: YTD / 12M / Mes)  │
│    €1.234,56                                                 │
│    └ Intereses y comisiones · €234 (19%)  [coste real]      │
│    └ Capital amortizado · €1.000 (81%)    [reduce deuda]    │
├─────────────────────────────────────────────────────────────┤
│ ③ Composición            ④ Evolución mensual                │
│   donut por tipo            barras apiladas 12m              │
│   - Hipoteca 70%            - cap. amort.                    │
│   - Tarjeta 20%             - intereses                      │
│   - Préstamo 10%                                             │
├─────────────────────────────────────────────────────────────┤
│ ⑤ Cuotas recurrentes detectadas                             │
│   Hipoteca BBVA · 850 € · mensual · cat. Hipoteca           │
│   Tarjeta Visa · 120 € · mensual · cat. Tarjeta crédito     │
├─────────────────────────────────────────────────────────────┤
│ ⑥ Detalle por contrato (Capa 2) — colapsable                │
│    [si hay liabilities]                                     │
│    Hipoteca BBVA · 145.000 € pendientes · TIN 3.5% · ...    │
│    [Pagar cuota] [Ver cuadro]                               │
│                                                              │
│    [si NO hay liabilities pero hay categoría debt]          │
│    💡 Para que tu patrimonio refleje la deuda completa,     │
│       vincula tu contrato. [Crear contrato vinculado]       │
└─────────────────────────────────────────────────────────────┘
```

### Componentes nuevos / modificados

**Nuevo** `apps/web/components/debt/effort-ratio-section.tsx`:
- Toggle entre estricta y ampliada (usa `useState` local).
- Gauge horizontal con thresholds 30% / 35%.
- Captura "X € de Y € netos mensuales".
- Educative tooltip explicando ampliada vs estricta.

**Nuevo** `apps/web/components/debt/payments-summary-card.tsx`:
- Selector de rango YTD / 12M / Mes (`<select>` o segmented control).
- KPI grande "Pagos a deuda".
- Desglose intereses / capital con barra horizontal apilada y % de cada.
- Tooltip educativo en "Capital amortizado": *"Este dinero reduce la
  deuda pendiente. Sale de tu bolsillo pero construye patrimonio."*

**Nuevo** `apps/web/components/debt/debt-composition-donut.tsx`:
- Donut Recharts con colores diferenciados por tipo (mortgage,
  loan, credit_card, other).
- Hover muestra `{type} · {amount} · {%}`.
- Centro vacío con total cuando no hay hover.

**Nuevo** `apps/web/components/debt/debt-monthly-evolution.tsx`:
- Bar chart apilado con 12 meses (Recharts BarChart con dos `<Bar>`
  apilados: intereses + capital).
- ReferenceLine vertical en el mes actual.

**Nuevo** `apps/web/components/debt/recurring-quotas-list.tsx`:
- Lee `fixed_expenses` filtrado por `category.role IN (DEBT_PAYMENT,
  DEBT_INTEREST)`. Reutiliza el detector existente. Solo render +
  link al contrato vinculado si lo hay.

**Modificado** `apps/web/components/debt/debt-list.tsx`:
- Pasa a ser la **Capa 2** dentro de `/debt`. Sin cambios
  funcionales — solo se mueve dentro de una `<details>` o `<section>`
  colapsable bajo "Detalle por contrato".
- Cuando `liabilities.length === 0` Y `category-summary.recurring_quotas.length > 0`,
  renderiza el CTA "Vincular contrato" en lugar del empty state actual.

**Modificado** `apps/web/app/(app)/debt/page.tsx`:
- Composición completa nueva. Mantiene el header pero sustituye
  `<DebtHealthCard />` por las nuevas cards.
- `DebtTrendChart` (la serie histórica + proyección) **se mantiene
  solo si hay liabilities** — pasa a ser parte de Capa 2.

**Modificado** `apps/web/components/analysis/position-hero.tsx`:
- La sección "②  Salud de deuda" cambia el cálculo del KPI: usa
  `effort_ratio_strict` en lugar de `dti_ratio`. Mismo gauge, mismas
  bandas nuevas. Label "Tasa de esfuerzo".

**Sin cambios**: `apps/web/app/(app)/personal-finance/accounts/[id]/amortization/page.tsx`
queda igual en 30.3. Se mueve en 30.4 a `/debt/contracts/[id]/schedule`.

### Hooks shared nuevos

`packages/services/src/query/hooks/useDebtCategorySummary.ts`:

```ts
export function useDebtCategorySummary(range: 'ytd' | '12m' | 'month' = 'ytd') {
  return useQuery({
    queryKey: keys.debt.categorySummary(range),
    queryFn: () => debtApi.categorySummary(range),
    staleTime: 60_000,
  });
}
```

### Strings de UI clave

| Token | Texto |
|---|---|
| `debt.effort.strict.label` | "Tasa de esfuerzo (estricta)" |
| `debt.effort.strict.help` | "% de tus ingresos netos mensuales que va a cuotas de deuda. Banco de España recomienda no superar el 35%." |
| `debt.effort.extended.label` | "Tasa de esfuerzo (ampliada)" |
| `debt.effort.extended.help` | "Incluye también tus gastos fijos confirmados (suministros, seguros, suscripciones). Da una idea más realista de tu margen disponible." |
| `debt.payments.title` | "Pagos a deuda" |
| `debt.payments.interests` | "Intereses y comisiones" |
| `debt.payments.interests.help` | "El coste real de tu deuda. Dinero que no recuperas." |
| `debt.payments.capital` | "Capital amortizado" |
| `debt.payments.capital.help` | "Reduce tu deuda pendiente. Sale de tu bolsillo pero construye patrimonio." |
| `debt.link.cta` | "Vincular contrato" |
| `debt.link.help` | "Para que tu patrimonio refleje la deuda completa, asocia esta cuota a un contrato con saldo pendiente." |

### Tests web

`apps/web/components/debt/__tests__/effort-ratio-section.test.tsx`:
- Toggle estricta → ampliada cambia el % mostrado.
- Banda visual cambia con el ratio (verde / ámbar / rojo).

`apps/web/components/debt/__tests__/payments-summary-card.test.tsx`:
- El desglose interés/capital suma siempre el total.
- Si `interests_and_fees === 0`, el desglose colapsa a "Sin intereses
  pagados todavía".

`apps/web/app/(app)/debt/__tests__/page.test.tsx`:
- Usuario sin liabilities pero con summary: renderiza Capa 1 completa,
  Capa 2 muestra CTA "Vincular contrato".
- Usuario con liabilities: ambas capas visibles.
- Usuario sin nada: empty state.

---

## PHASE-30.4 — Capa 2 condensada + integración

### Cuadro francés condensado

**Nueva ruta**: `/debt/contracts/[id]/schedule`. La antigua
`/personal-finance/accounts/[id]/amortization` redirige.

**Componente nuevo** `apps/web/components/debt/schedule-condensed.tsx`:

```
Año 2026 — €9.600 · €1.500 intereses · saldo final €138.500   [▾]
Año 2027 — €9.600 · €1.420 intereses · saldo final €131.420   [▾]
...
```

Click en `[▾]` expande las 12 filas del mes para ese año. Mantiene el
componente legacy `amortization-table` accesible vía un toggle "Ver
detalle mensual completo" para el usuario nostálgico.

**Highlights**:
- Año actual marcado con border copper.
- Mes actual dentro del año expandido marcado con `surface-muted`.
- Cuota del mes actual destacada en header del año.

### Vinculación contrato-categoría

**Backend**:
- Migración Alembic: `accounts.category_id UUID NULL FK categories(id)
  ON DELETE SET NULL`.
- `accounts/schemas.py`: `AccountCreate`/`AccountUpdate` aceptan
  `category_id` opcional. Validar que la categoría existe y pertenece
  al usuario, y que su `role IN (DEBT_PAYMENT, DEBT_INTEREST)` (si no,
  400 con mensaje claro).

**Frontend**:
- `account-form-fields.tsx`: cuando el tipo es liability, mostrar un
  `<select>` "Categoría de pagos vinculada (opcional)" con las
  categorías del usuario que tienen `role IN (DEBT_PAYMENT,
  DEBT_INTEREST)`.
- En la lista de Capa 2, mostrar la categoría vinculada como chip.
- En la card de Capa 1 (donut composición), permitir click en un
  segmento → navegar a la lista de contratos vinculados a esa
  categoría.

### Detección de cuota recurrente sin vinculación

Cuando `recurring_quotas[i].fixed_expense_id` está asociado a una
categoría con `role=DEBT_PAYMENT` **y** no existe ninguna
liability con `category_id = recurring_quotas[i].category_id`:

- Mostrar en la lista de Capa 2 un item especial: "Hipoteca BBVA · 850
  €/mes detectada. ¿Quieres crear el contrato vinculado?"
- CTA abre un modal pre-rellenado con datos detectados (merchant →
  name, amount → cuota observada, currency, category_id). Pide al
  usuario el resto (saldo pendiente, TIN, plazo, fecha inicio).

### Operación financiada — bajada de protagonismo

`apps/web/components/transfers/convert-to-debt-dialog.tsx`: se mantiene
intacto. Solo cambia que **no aparece nunca en `/debt`**, vive
exclusivamente en detalle de tx. Esto confirma la decisión de "feature
secundaria de Capa 2".

### Tests

- `test_accounts.py`: liability con `category_id` válida → OK.
- `test_accounts.py`: liability con `category_id` cuya `role=GENERIC` →
  400 con mensaje claro.
- E2E manual: crear hipoteca con categoría vinculada → categoría
  aparece en card de Capa 2.
- E2E manual: tener una cuota recurrente sin contrato → ver el item
  especial → flujo de creación funciona.

---

## PHASE-30.5 — Mobile parity (opcional)

Replicar 30.3 + 30.4 en `apps/mobile/`. Diferido por defecto. Si se
ejecuta, sigue el patrón habitual del proyecto (mismas decisiones de
diseño, RN equivalent components, tokens compartidos).

---

## PHASE-30.6 — Selector de divisa del header → endpoints de deuda

Polish post-MVP. El selector global de divisa del header ya no se
ignoraba en `/debt`: ahora se propaga como `target_currency` a los
tres endpoints del módulo (`category-summary`, `debt-health`,
`debt-history`), con conversión per-tx (igual que dashboard). Sin
`convertAll` se mantiene el modo native. Se eliminaron además literales
de enum filtrados en la respuesta. (Commit `a3b954e`.)

---

## PHASE-30.7 — Selector temporal unificado + donut por cuenta vinculada

Dos cambios de polish que cierran inconsistencias detectadas tras
30.6:

### 1. Rango temporal `month / quarter / year`

El selector de `/debt` usaba los valores legacy `ytd | 12m | month`,
distintos del `StitchPeriodToggle` del dashboard y análisis
(`month | quarter | year`). Se alinea el contrato completo:

- `DebtTimeRange` pasa a `'month' | 'quarter' | 'year'` (default `year`).
- `_resolve_range` (service): `month` = mes en curso (1 bucket);
  `quarter` = trimestre natural en curso (Q1 Ene-Mar … Q4 Oct-Dic, 3
  buckets); `year` = YTD (enero..mes actual, `today.month` buckets).
- Propagado a `schemas.py`, `router.py` (default), tipos shared
  (`debt.ts`), `endpoints/debt.ts`, `useDebt.ts`, `query/keys.ts`.
- UI web y mobile: labels `Mes / Trimestre / Año` y restyle del
  `RangeSelector` como espejo visual de `StitchPeriodToggle`.

### 2. Donut de composición por tipo: señal primaria = cuenta vinculada

Antes el bucket (`mortgage / loan / credit_card / other`) se infería
solo del nombre de la categoría. Ahora:

- **Señal primaria**: `account.type` de la liability vinculada a la
  categoría (`accounts.category_id`, PHASE-30.4), vía subquery escalar
  correlacionada en `aggregate_debt_payments_by_category`. Si la
  categoría apunta a una `mortgage`, su bucket es `mortgage` con
  certeza, etc.
- **Fallback** (sin cuenta vinculada): matching por nombre, pero con
  **`loan` chequeado ANTES que `mortgage`**, para que la categoría
  seed "Préstamos e hipotecas" caiga en `loan` (la usan mayormente
  usuarios sin hipoteca real). Una hipoteca explícita ("Hipoteca
  BBVA") no contiene "préstamo" → cae en `mortgage`.

### Archivos

```
backend/app/modules/personal_finance/debt/{schemas,service,router,repository}.py
backend/tests/test_debt_category_summary.py   [tests rango + clasificación]
packages/types/src/models/debt.ts
packages/services/src/api/endpoints/debt.ts
packages/services/src/query/hooks/useDebt.ts
packages/services/src/query/keys.ts
apps/web/app/(app)/debt/page.tsx
apps/web/components/debt/payments-summary-card.tsx
apps/mobile/app/(modules)/debt/index.tsx
apps/mobile/components/debt/payments-summary-card.tsx
internal_docs/api/endpoints.md
```

### Tests nuevos / actualizados

- `test_summary_prestamos_hipotecas_seed_classified_as_loan` — la
  categoría seed cae en `loan` (regresión loan-first).
- `test_summary_linked_account_type_overrides_name_match` — cuenta
  `mortgage` vinculada gana sobre nombre que matchea "préstamo".
- `test_summary_quarter_returns_three_monthly_buckets` — `quarter`
  devuelve 3 buckets.
- `test_summary_year_returns_ytd_buckets` — `year` devuelve
  `today.month` buckets.
- Resto de tests migrados de `range=ytd|12m` → `year|quarter`.

### Verificación

- [x] `pytest tests/test_debt_category_summary.py tests/test_debt.py` — 43 verde.
- [x] `mypy` sin errores nuevos (los 13 pre-existentes en
      `conversion.py` / `repository.py` / `service.py` ya estaban en HEAD).
- [x] `pnpm typecheck`, `pnpm lint`, `pnpm test` verdes.

### Lección

Cuando una pista (nombre de categoría) puede mentir y existe una señal
fuerte (cuenta vinculada con `type` explícito), usar la señal fuerte
como primaria y la pista como fallback. Análogo a la lección de
PHASE-28 (dirección de transferencia explícita > inferida).

---

## PHASE-30.8 — Navegador de período (Capa 1) + KPIs period-scoped

El selector temporal de 30.7 elegía la *granularidad* (mes / trimestre
/ año) pero siempre anclaba al período en curso. 30.8 añade un
**navegador** para moverse a períodos pasados sin salir de la
granularidad elegida, y reescala los KPIs a la ventana visible.

- **Ancla compartida (`anchor`)**: un día cualquiera dentro del período
  objetivo. `_period_window(anchor, range)` es la fuente ÚNICA de verdad
  del `range_start`/`range_end`, usada por la serie, la tasa de esfuerzo
  y los ingresos medios — todos miran la misma ventana.
- **Flechas con clamp a datos**: `range_start`/`range_end` de la
  respuesta (`debt_movement_bounds`) acotan hasta dónde puede navegar el
  usuario; no hay flechas hacia meses sin movimientos.
- **KPIs period-scoped**: `monthly_income_avg` y
  `monthly_debt_payment_avg` se promedian sobre los meses **cerrados**
  del período (se excluye el mes en curso para no diluir la media con un
  mes incompleto). La tasa de esfuerzo se deriva de esa misma ventana.

(Commit `96087b1`.)

---

## PHASE-30.9 — Serie diaria del saldo de deuda (`range='month'`)

Con `range='month'` la serie mensual degeneraba en **una sola barra**
(un único bucket = el mes). Inútil. 30.9 la sustituye por una vista
diaria que modela la **evolución del saldo de deuda dentro del mes**.

### Backend

- **`DailyDebtPoint`** (schema): `{ day, emitida, amortizado, interest,
  balance }`. Campo `daily_series: list[DailyDebtPoint] | None` en
  `DebtCategorySummary`, poblado **sólo** con `range='month'` (`None`
  para quarter/year, que usan `monthly_series`).
- **`_build_daily_series`** (service) orquesta dos modos:
  - **Con cuentas-pasivo** (Capa 2): línea de `balance` = apertura
    agregada de los pasivos + *carry* (`liability_signed_before`, Σ
    firmada antes del mes) + Σ flujos diarios. `emitida` ↑ (cargos que
    suben deuda: expense/sin-categoría) y `amortizado` ↓ (entradas que
    la bajan: income) vienen de `daily_liability_flows`. El saldo se
    clampa a ≥ 0.
  - **Sin cuentas-pasivo** (fallback): `balance=None` (no hay línea) y
    `amortizado` toma los pagos de capital categorizados
    (`DEBT_PAYMENT`) de `daily_category_flows` — el chart sigue siendo
    útil aunque el usuario no haya declarado contratos.
  - `interest` (informativo) = Σ `DEBT_INTEREST` del día
    (`daily_category_flows`); se paga en cash y NO mueve el principal.
- Mismo split de signo que `get_balances_for_user`/`debt_history`
  (expense/sin-cat suman al saldo de un pasivo, income resta) y mismas
  fronteras UTC que el resto de la serie. Respeta `target_currency`
  (per-tx) igual que 30.6.

### Frontend

- **`DebtDailyEvolution`** (web Recharts `ComposedChart` + mobile
  gifted-charts), nuevo en `apps/{web,mobile}/components/debt/`. Combo:
  línea de `balance` (eje izq.) + barras `emitida`/`amortizado` (eje
  der.); el interés va en el tooltip.
- `/debt` (web + mobile) hace swap condicional: `range='month'` →
  `DebtDailyEvolution`, en otro caso `DebtMonthlyEvolution`. Lazy-loaded
  en web (`dynamic`, `ssr:false`).

### Tests

- `test_daily_series_tracks_balance_emission_and_payment` — línea de
  saldo + emisión/amortización con cuentas-pasivo.
- `test_daily_series_fallback_without_liabilities` — `balance=None` y
  amortizado = pagos categorizados.
- `test_daily_series_null_for_year_range` — `daily_series=None` fuera de
  `month`.

### Lección

Cuando una granularidad colapsa una serie en un solo punto (mes = 1
bucket), no muestres una barra única: cambia el modelo de la vista
(saldo diario) para que la dimensión temporal siga aportando información.

---

## Archivos clave (vista consolidada)

### Backend
```
backend/alembic/versions/m0a14e6097c3d_category_role.py             [nuevo]
backend/alembic/versions/n1b25f8a3d9e4_account_category_link.py     [nuevo, 30.4]
backend/app/modules/personal_finance/categories/{models,schemas,service}.py
backend/app/modules/personal_finance/seed/dataset.py
backend/app/modules/personal_finance/accounts/{models,schemas,service,debt_health,debt_history}.py
backend/app/modules/personal_finance/debt/__init__.py               [nuevo]
backend/app/modules/personal_finance/debt/{router,service,repository,schemas}.py [nuevo]
backend/app/modules/personal_finance/transactions/repository.py
backend/app/main.py
backend/tests/test_categories.py
backend/tests/test_debt.py
backend/tests/test_debt_category_summary.py                         [nuevo]
backend/tests/test_accounts.py
```

### Frontend shared
```
packages/types/src/models/category.ts
packages/types/src/models/debt.ts
packages/types/src/dto/debt.dto.ts                                  [nuevo]
packages/services/src/api/endpoints/debt.ts                         [nuevo]
packages/services/src/query/hooks/useDebtCategorySummary.ts         [nuevo]
packages/services/src/query/keys.ts
```

### Frontend web
```
apps/web/components/debt/effort-ratio-section.tsx                   [nuevo]
apps/web/components/debt/payments-summary-card.tsx                  [nuevo]
apps/web/components/debt/debt-composition-donut.tsx                 [nuevo]
apps/web/components/debt/debt-monthly-evolution.tsx                 [nuevo]
apps/web/components/debt/recurring-quotas-list.tsx                  [nuevo]
apps/web/components/debt/schedule-condensed.tsx                     [nuevo]
apps/web/components/debt/debt-list.tsx                              [refactor: Capa 2]
apps/web/components/dashboard/debt-health-card.tsx                  [legacy, dashboard solo]
apps/web/components/analysis/position-hero.tsx                      [efforto en lugar de DTI]
apps/web/components/accounts/account-form-fields.tsx                [+ category_id selector]
apps/web/app/(app)/debt/page.tsx                                    [redesign completo]
apps/web/app/(app)/debt/contracts/[id]/schedule/page.tsx            [nuevo]
apps/web/app/(app)/personal-finance/accounts/[id]/amortization/page.tsx [→ redirect]
```

## Endpoints añadidos

- `GET /debt/category-summary?range=month|quarter|year` (def `year`,
  PHASE-30.7; `&anchor=YYYY-MM-DD` opc desde PHASE-30.8 para navegar a
  períodos pasados; `target_currency` opc desde PHASE-30.6) — Capa 1
  completa. Desde PHASE-30.9 incluye `daily_series` (sólo `range=month`)
  con la evolución diaria del saldo de deuda + `range_start`/`range_end`
  para acotar el navegador.

## Endpoints modificados

- `GET /accounts/debt-health` — bandas reclasificadas (30/35%),
  `time_to_payoff` usa schedule. Backward compatible en shape.

## Endpoints legacy

- `GET /accounts/debt-history` — se mantiene, ahora consumido solo por
  Capa 2 cuando hay liabilities.

## Migraciones

- `m0a14e6097c3d_category_role.py` (30.1) — enum + columna + backfill +
  índice parcial.
- `n1b25f8a3d9e4_account_category_link.py` (30.4) — `accounts.category_id`
  FK nullable.

## Verificación

- [ ] `pytest backend/tests/` verde, incluyendo nuevos suites.
- [ ] `pnpm typecheck` verde en los 4 paquetes.
- [ ] `pnpm lint` verde.
- [ ] `pnpm test` web verde (incluye nuevos component tests).
- [ ] Migraciones `up` + `down` reversibles en BD local.
- [ ] Smoke manual 30.1: usuario nuevo, seed asigna roles correctos.
- [ ] Smoke manual 30.2: usuario con 3 meses de extractos BBVA
      categorizados, /debt/category-summary devuelve KPIs coherentes
      sin liability accounts.
- [ ] Smoke manual 30.3: `/debt` muestra Capa 1 completa para usuario
      sin liabilities.
- [ ] Smoke manual 30.4: vincular categoría con liability, ver chip y
      navegación por donut.

## Decisiones tomadas (referencia rápida)

- **Dos capas en una página**, no dos módulos. Coherencia IA.
- **`role` enum**, no flag booleano. Unifica `is_transfer` y elimina
  `INTEREST_CATEGORY_NAMES`. Migración no destructiva.
- **Bandas 30% / 35%** (Banco España, sobre ingresos netos), no 36/43%
  (US, sobre brutos). Renombre a "Tasa de esfuerzo".
- **"Pagos a deuda" como KPI principal** (suma flujo entero, incluye
  capital), con desglose interno intereses/capital. Más cercano a la
  intuición del usuario que "coste".
- **Trampa del patrimonio neto aceptada** con UI explícita: usuario sin
  liability vinculada subestima la deuda en patrimonio. Mitigado con
  CTA "Vincular contrato".
- **Operación financiada (PHASE-24) baja a feature secundaria** — solo
  desde detalle de tx, sin promoción en `/debt`.
- **Cuadro francés condensado por defecto**, mensual expandible.
- **Mobile aplazado** a 30.5. La parity no bloquea el rediseño web.

## Limitaciones que quedan tras PHASE-30

- Pendiente PHASE-31: deprecar columna `categories.is_transfer` una vez
  todos los callers consumen `role`.
- Pendiente PHASE-31: alertas proactivas cuando `effort_ratio_strict`
  cruza una banda (replicar PHASE-14.5 budget over).
- Pendiente PHASE-32 (opcional): simulador "antes-de-firmar" sobre la
  infra Capa 1.
- Pendiente PHASE-33 (opcional): detector de oportunidades de
  refinanciación (requiere fuente externa de tipos).
- Mobile sigue con el módulo antiguo hasta PHASE-30.5.

## Próxima fase

Sin fase encadenada decidida. Candidatos en orden de impacto:

1. **PHASE-30.5** — Mobile parity. Coherencia cross-platform.
2. **PHASE-31** — Alertas proactivas + deprecación `is_transfer`.
3. **PHASE-32** — Simulador "antes-de-firmar" (la pieza de
   diferenciación real del producto).

---

## Anexo — Wireframe textual completo de `/debt` rediseñada

Ver `internal_docs/design-explorations/debt-redesign-30/wireframe.md`.
