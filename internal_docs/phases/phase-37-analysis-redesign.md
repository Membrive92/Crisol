# PHASE-37 — Rediseño módulo Análisis + saneamiento de deuda

**Estado**: ✅ completada · en `main` (push directo `89eea70`, 2026-07-12, sin PR)
**Rama**: `feat/phase-37-analysis-redesign`
**Commits**: `397f3db` (37.1) · `ba5123f`+`bdd0574` (37.2) · `e7f9331` (37.3) ·
`da3d376` (bugfix Bizum) · `be548f5` (deuda) · `ed61adb` (37.4) · `e141cf0` (37.5)

## Objetivo

Rediseñar `/analysis` para que las tarjetas de *stock* (patrimonio, deuda)
ganen dimensión temporal (Δ + serie) en vez de ignorar el selector de
período, aprovechar el ancho de pantalla, y añadir analítica derivada
(gasto estructural vs puntual, proyección de fin de mes, insights no
redundantes). En el camino se sanearon dos bugs de datos reales (una
categorización ciega a la dirección y el módulo de deuda leyendo el interés
de transacciones inexistentes).

Plan completo (con ADR informal y wireframes) en
[`../improvements/phase-37-analysis-redesign-plan.md`](../improvements/phase-37-analysis-redesign-plan.md).

## Qué se implementó

### 37.1 — Serie temporal de patrimonio (`397f3db`)
- `GET /accounts/position-history`: activos/pasivos/neto por mes + Δ-periodo.
- `signed_amount_expr()` compartida (una sola fuente del signo del saldo,
  para que `/balances` y la serie no diverjan).
- Δ-periodo en `/dashboard/summary`.

### 37.2 — KPI strip + layout (`ba5123f` + `bdd0574`)
- Franja de 5 KPIs (patrimonio+sparkline, Δ, esfuerzo, flujo, ahorro),
  respetando el toggle `includeDebtInNetWorth`.
- Grid a ancho completo (`max-width 2400`), cuentas colapsables, donut top-6.
- `scaleFont()` (escala web-only 1.15×) en tokens + chrome. Fix `-0,00 €`.

### 37.3 — Gasto estructural vs puntual (`e7f9331`)
- Módulo `analytics/` nuevo: heurística de recurrencia (`recurrence.py`) +
  `GET /analytics/expense-structure` (estructural/puntual + tasa de ahorro
  dual). Columna `transactions.is_exceptional` (tri-estado) + migración.
- Web: control `[Todo|Estructural|Puntual]`, tasa estructural en el tile,
  toggle "Gasto puntual" tri-estado en el detalle de la tx.

### bugfix — concepto de dirección ambigua en imports (`da3d376`)
- Un bank-mapping aprendido `'bizum' → Bizum recibido` etiquetaba como
  ingreso los BIZUM salientes. Fix: el autoaprendizaje **no fija** una
  equivalencia para conceptos que aparecen con cargo **y** abono en el lote.
  Generaliza la lección PHASE-32 al paso de aprendizaje. Data-fix de 10 filas.

### deuda — interés y deuda viva desde el cuadro (`be548f5`)
- El módulo derivaba interés/pagos de transacciones en categorías
  `DEBT_INTEREST`/`DEBT_PAYMENT`, estructuralmente vacías (el banco no
  desglosa el interés). Fix **MUX por pasivo** (cuadro XOR transacciones):
  debt-health (`interest_paid_ytd` + contractual + restante + `debt_by_type`),
  category-summary (card + barras + effort ratio), debt-history (interés
  histórico), y `AccountBalance.monthly_payment` (cuota real de tarjetas
  financiadas). Web `/debt`: franja de KPIs, donut de deuda viva, conteo sin
  hijas. Follow-up: `debt_movement_bounds` combina tx + cuadro para el
  navegador de período.

### 37.4 — Proyección fin de mes + runway (`ed61adb`)
- `GET /analytics/month-outlook`: cargos comprometidos del mes (gastos fijos
  + cuotas sin pagar) + runway (líquido / gasto estructural mensual de 37.3).
- Web: card "Fin de mes". Revisión adversarial aplicada (ver Decisiones).

### 37.5 — Smart Insights v2 (`e141cf0`)
- Regla de no-redundancia: se eliminan los insights que duplican un KPI
  ("saldo neto vs anterior", "tasa de ahorro"). Generadores derivados:
  concentración de gasto, impacto de puntuales (37.3), cargo próximo (37.4).
  Máximo 3, por prioridad. Todo client-side (privacidad de `/analysis`).

## Endpoints añadidos
- `GET /accounts/position-history` (37.1)
- `GET /analytics/expense-structure` (37.3)
- `GET /analytics/month-outlook` (37.4)
- `DebtHealthKpis` gana `debt_by_type`, `interest_scheduled_total`,
  `interest_remaining`; `AccountBalance` gana `monthly_payment` (deuda).

## Migraciones
- `c6s92u4rp6t5s1_transactions_is_exceptional` (37.3). Nullable, reversible.
  Aplicada a dev; pendiente en producción.

## Decisiones tomadas
- **Los stocks ganan Δ+sparkline, no filtro por rango** (37.1/37.2).
- **MUX por pasivo, no aditivo** (deuda, 37.4): el interés/capital de una
  deuda sale del cuadro **o** de transacciones, nunca la suma — evita el
  doble conteo "dos fuentes de verdad" (lección PHASE-34).
- **month-outlook sin MUX por `account_id`** (revisión adversarial 37.4): el
  dedup por cuenta over-excluía cargos legítimos en tarjetas financiadas y no
  capturaba el doble conteo real (el pago se cobra del banco). Se eliminó.
- **Runway con numerador y denominador en el mismo alcance de divisa**;
  tasas ausentes se descartan (no se suma valor en otra divisa).
- **Insights con no-redundancia declarada** (37.5).

## Verificación
- [x] Backend `pytest` (642) · `mypy` (137) · `ruff` verdes.
- [x] Frontend `typecheck`/`lint`/`test` (95 web) verdes.
- [x] Cada cálculo verificado contra datos reales del usuario
      (19.942,80 € deuda viva · 371,59 € interés YTD · 433,35 € comprometido).
- [x] Revisión adversarial (workflows) en Bizum, deuda y month-outlook.

## Limitaciones conocidas
- `position-history` y los agregados de deuda sólo cuentan la divisa de
  referencia (histórico multi-divisa requiere tasas por fecha).
- La heurística estructural/puntual tendrá falsos positivos el primer mes de
  un recurrente nuevo (mitigado por el override).
- month-outlook no arrastra el backlog de meses anteriores (decisión de
  diseño: un resumen mensual no lista 6 meses de impagos).
- Guard defensivo padre/hija en debt-health (doble conteo si un cargo espejo
  cae sobre la tarjeta padre): latente, sin defecto actual — follow-up.
- La serie de patrimonio móvil (37.6) no convierte divisas (modo nativo),
  misma limitación que web.

### 37.6 — Mobile parity (✅)
Espejo de los features nuevos en la pantalla de análisis RN (la capa de datos
—hooks/tipos— ya era cross-platform): card "Fin de mes" (37.4), Smart Insights
v2 (37.5), sub-filtro `[Todo|Estructural|Puntual]` en el donut (37.3),
composición de deuda + interés contractual/restante en la DebtHealthCard, y
card de evolución de patrimonio (37.1, `LineChart`). Los Δ vs periodo previo
(37.2) ya estaban en `KpiCards`. Verde: typecheck + lint + 18 tests jest-expo.

## Próxima fase
Ninguna pendiente de PHASE-37. Follow-ups sueltos: guard defensivo padre/hija
(latente) y saldo de apertura de BBVA (data-fix del usuario).
