# ADR-0003 — Módulo deuda: arquitectura en dos capas (flujo + contrato)

**Estado**: propuesta
**Fecha**: 2026-05-25
**Fase**: PHASE-30

## Contexto

El módulo deuda introducido en PHASE-22 y ampliado en PHASE-24 modela la
deuda como **liability accounts** (`accounts.nature = LIABILITY`) con
campos opcionales `apr` / `term_months` / `start_date` para construir un
cuadro francés y derivar KPIs (DTI, weighted APR, time-to-payoff,
interest YTD). Todo el módulo está hoy condicionado a que el usuario
cree y rellene una cuenta liability con esos datos.

El problema observado:

1. **Fricción de onboarding alta**. Para que `/debt` aporte algo, el
   usuario tiene que crear una cuenta de deuda y conocer TIN, plazo y
   fecha de inicio. La mayoría no lo hará — importará su extracto y
   dejará que el rules engine asigne sus cuotas a las categorías
   "Préstamos e hipotecas" / "Tarjeta de crédito" / "Intereses *".
2. **El módulo no aporta valor en ese flujo mayoritario**. Si no hay
   liability account con APR, ni hay KPIs (`monthly_debt_payment`,
   `weighted_apr`, `dti_ratio` salen vacíos), ni hay schedule, ni hay
   serie temporal proyectada. El usuario que solo categoriza no ve nada.
3. **Las categorías ya capturan el flujo real de deuda** del usuario
   (cuotas + intereses + comisiones), pero el módulo deuda no las
   consume — vive paralelo a ellas.

## Decisión

El módulo deuda se reorganiza en **dos capas** que coexisten en la
misma página `/debt`. La fuente de verdad **principal** del módulo pasa
a ser el flujo derivado de categorías marcadas como deuda. Las
liability accounts pasan a ser una capa de enriquecimiento opcional.

### Capa 1 — Análisis por categoría (default, sin onboarding)

Fuente: transacciones cuya categoría tiene `role IN (DEBT_PAYMENT,
DEBT_INTEREST)`. Calcula y muestra:

- **Tasa de esfuerzo** (estricta y ampliada con toggle), basada en
  flujo real, no en cuotas teóricas. Bandas Banco España 30% / 35%
  sobre ingresos **netos**.
- **Pagos a deuda este año** (Σ del flujo en categorías de deuda),
  expandible a su desglose en *intereses y comisiones* (coste real)
  vs *capital amortizado*.
- **Composición**: % de los pagos por tipo (préstamo / hipoteca /
  tarjeta) — donut.
- **Evolución mensual**: serie temporal del flujo a deuda últimos 12
  meses.
- **Top cuotas recurrentes** detectadas por el módulo `fixed_expenses`
  filtradas por categoría de deuda.

Funciona desde el primer día con datos que el usuario ya está
produciendo al importar y categorizar. No requiere ninguna cuenta
liability.

### Capa 2 — Detalle por contrato (opt-in, usuario avanzado)

Fuente: liability accounts. Aporta lo que ya existe:

- Saldo pendiente real por contrato.
- Cuadro francés **condensado** (resumen anual + expandir al mes).
- Time-to-payoff exacto (a partir del schedule, no proyección lineal).
- Wizard de pago con split principal/intereses.
- Aporte al patrimonio neto correcto.
- Conversión de operación financiada (PHASE-24) — feature secundaria
  visible solo en detalle de tx, no promovida en `/debt`.

Se renderiza en `/debt` solo si el usuario tiene al menos una
liability. Cuando no hay liabilities pero sí hay categoría de deuda
detectada, se muestra una nota explícita: *"Para que tu patrimonio
neto refleje la deuda real, vincula este contrato → [CTA]"*.

### Asociación entre capas

Una liability account puede vincularse opcionalmente a una categoría
mediante `accounts.category_id` (nuevo campo, nullable FK). Cuando la
asociación existe:

- En Capa 1, los pagos a esa categoría enriquecen la fila de Capa 2
  del contrato vinculado (cuota observada vs teórica, % desviación).
- En Capa 2, el saldo pendiente se contrasta con la suma de capital
  amortizado en la categoría asociada.
- **No hay doble cómputo**: el flujo se cuenta una sola vez en Capa 1;
  Capa 2 lo reusa como sub-vista.

## Consecuencias

- ✅ El módulo `/debt` aporta valor desde el primer extracto importado,
  sin onboarding adicional.
- ✅ KPI principal (tasa de esfuerzo) se calcula desde flujo real, no
  desde cuotas teóricas — refleja lo que el usuario paga, no lo que
  debería pagar según el contrato.
- ✅ Se elimina el frozenset `INTEREST_CATEGORY_NAMES` y el flag ad-hoc
  `Category.is_transfer`. Pasan a un único enum `categories.role` que
  unifica las clasificaciones especiales (transfer, debt_payment,
  debt_interest, generic).
- ✅ Bandas 30% / 35% (Banco España) en lugar de 36% / 43% (US mortgage
  lending), apropiado para el mercado objetivo.
- ✅ Toda la funcionalidad de Capa 2 (cuadro francés, wizard,
  installments, KPIs por contrato) se conserva intacta.
- ⚠️ **Trampa aceptada**: cuando un usuario tiene una hipoteca y la
  categoriza pero no crea liability account, su **patrimonio neto
  subestima la deuda** (la cuota aparece como gasto del mes, pero el
  saldo pendiente no entra al `total_liabilities`). Se mitiga con una
  nota UX explícita en `/debt` y un CTA "Vincular contrato" cuando se
  detecta categoría de deuda recurrente sin liability asociada. La
  alternativa de inferir el saldo desde la fecha+cuota observadas se
  descarta — produce datos medio-ficticios incompatibles con el
  principio de precisión del producto.
- ⚠️ El KPI "Coste real" pasa a ser **"Pagos a deuda"** (suma todo) con
  desglose interno "intereses + comisiones" vs "capital amortizado".
  Esto respeta la perspectiva de cashflow del usuario, pero requiere
  educar visualmente sobre la diferencia entre coste financiero y
  capital amortizado (la segunda no es coste real, construye
  patrimonio).
- ⚠️ El `weighted_apr` y `time_to_payoff` solo aplican a Capa 2.
  Desaparecen del KPI principal cuando no hay liabilities.
- 🔜 Migración de páginas hacia el módulo top-level: `/personal-finance/
  accounts/{id}/amortization` → `/debt/contracts/{id}/schedule`. Con
  redirects.
- 🔜 Mobile parity: PHASE-30.5 (fuera del MVP de redesign).

## Alternativas descartadas

- **Eliminar las liability accounts y basar todo en categorías**. Se
  pierde el patrimonio neto correcto del lado deuda — incompatible con
  la promesa de PHASE-22. También se pierden cuadro francés, wizard
  atómico, conversión de op financiada. Aproximación demasiado
  destructiva para resolver un problema de onboarding.
- **Mantener la arquitectura actual y resolver onboarding con UI
  mejor**. No resuelve el caso real: el usuario que no quiere rellenar
  TIN/plazo. Después de un wizard "wizard-of-Oz" mejorado, seguiría sin
  recibir valor.
- **Inferir liability automáticamente al detectar cuota recurrente**
  con saldo estimado por fecha-cuota observadas. Produce datos
  ficticios con alta varianza. Rompe la confianza en el patrimonio
  neto si la estimación está mal calibrada. Descartada por el
  principio de precisión.
- **Capa 1 como módulo separado de Capa 2**. Fragmenta la IA: dos
  módulos top-level relacionados con deuda confunde al usuario. La
  decisión es **un módulo top-level con dos capas internas
  coherentes**.

## Referencias

- PHASE-22 — Módulo de deuda inicial (`phases/phase-22-debt-module.md`).
- PHASE-24 — Operaciones financiadas (`phases/phase-24-debt-from-source.md`).
- PHASE-23.1 — Flag `Category.is_transfer` (precedente para `role`).
- Banco de España, "Guía de acceso al préstamo hipotecario" — tasa de
  esfuerzo 30-35% sobre ingresos netos.
