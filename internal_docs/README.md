# Internal Docs — Crisol

Documentación viva del proyecto: arquitectura, metodología, estado por fase,
lecciones aprendidas y contexto de consulta para IA.

A medida que el proyecto avance, esta carpeta crecerá con documentos por fase,
ADRs (Architecture Decision Records), catálogo de endpoints y schema de BD.

## Índice

- **[HANDOFF.md](HANDOFF.md) — dónde estamos y qué sigue (empieza por aquí)**
- [architecture.md](architecture.md) — arquitectura del sistema
- [development-spec.md](development-spec.md) — metodología y fases
- [lessons.md](lessons.md) — errores y reglas aprendidas
- [backlog.md](backlog.md) — deuda técnica, limitaciones y follow-ups
- [investment-module-guide.md](investment-module-guide.md) — **guía completa del módulo Inversión**: lógica, decisiones, scripts y playbook de pruebas manuales
- [investment-threshold-divergences.md](investment-threshold-divergences.md) — umbrales y fórmulas: **cuaderno del usuario vs. motor** (manda el motor; aquí queda qué tocar si algún día se cambia)
- [api/endpoints.md](api/endpoints.md) — catálogo de endpoints
- [data-model/schema.md](data-model/schema.md) — estado del schema
- [decisions/](decisions/) — ADRs (decisiones arquitectónicas)
- [phases/](phases/) — un documento por fase completada
- [audits/](audits/) — auditorías (seguridad, arquitectura, UX, rendimiento)
- [ai-context/](ai-context/) — contexto de consulta bajo demanda para IA
  (glosario, ejemplos, evaluaciones de modelos, prompts guardados). Incluye
  [excel-analisis-empresas.md](ai-context/excel-analisis-empresas.md), la
  transcripción íntegra del cuaderno de metodología del usuario

---

## Estado de fases

Leyenda: ⏳ pendiente · 🚧 en curso · ✅ completada · ❌ bloqueada

### Fase 0 — Bootstrap

| Fase | Nombre               | Estado | PR  |
| ---- | -------------------- | ------ | --- |
| 0.0  | Setup inicial (docs) | ✅     | —   |
| 0.1  | Bootstrap monorepo   | ✅     | #1  |
| 0.2  | Bootstrap backend    | ✅     | —   |
| 0.3  | Bootstrap Ollama     | ✅     | —   |

### Fase 1 — Autenticación

| Fase | Nombre        | Estado | PR  |
| ---- | ------------- | ------ | --- |
| 1.1  | Auth backend  | ✅     | —   |
| 1.2  | Auth frontend | ✅     | —   |

### Fase 2 — Transacciones

| Fase | Nombre                | Estado | PR  |
| ---- | --------------------- | ------ | --- |
| 2.1  | Transactions backend  | ✅     | —   |
| 2.2  | Transactions frontend | ✅     | —   |

### Fase 3 — Dashboard

| Fase | Nombre             | Estado | PR  |
| ---- | ------------------ | ------ | --- |
| 3.1  | Dashboard backend  | ✅     | —   |
| 3.2  | Dashboard frontend | ✅     | —   |

### Fase 4 — Importación

| Fase | Nombre           | Estado | PR  |
| ---- | ---------------- | ------ | --- |
| 4.1  | Imports backend  | ✅     | —   |
| 4.2  | Imports frontend | ✅     | —   |
| 4.3  | PDF imports      | ✅     | —   |

### Fase 5 — IA: tickets

| Fase | Nombre            | Estado | PR  |
| ---- | ----------------- | ------ | --- |
| 5.1  | Receipts backend  | ✅     | —   |
| 5.2  | Receipts frontend | ✅     | —   |

### Fase 6 — Modularización del frontend

| Fase | Nombre            | Estado | PR  |
| ---- | ----------------- | ------ | --- |
| 6.1  | Module shell + PF | ✅     | —   |

### Fase 7 — Rediseño dashboard + layout shell

| Fase | Nombre                    | Estado | PR  |
| ---- | ------------------------- | ------ | --- |
| 7.0  | Design primitives + shell | ✅     | —   |
| 7.1  | Dashboard bento           | ✅     | —   |
| 7.2  | Transactions tabla        | ✅     | —   |
| 7.3  | Imports + Receipts polish | ✅     | —   |
| 7.4  | Mobile parity             | ✅     | —   |
| 7.5  | Analysis sub-tab          | ✅     | —   |
| 7.6  | Stitch fidelity rewrite   | ✅     | —   |

### Fase 8 — Multimoneda con conversión global

| Fase | Nombre                               | Estado | PR  |
| ---- | ------------------------------------ | ------ | --- |
| 8.1  | Currency rates backend               | ✅     | —   |
| 8.2  | Conversion frontend                  | ✅     | —   |
| 8.3  | Per-transaction conversion in SQL    | ✅     | —   |
| 8.4  | Transactions cross-currency + polish | ✅     | —   |

Plan completo en [phases/phase-8-roadmap.md](phases/phase-8-roadmap.md).

### Fase 9 — Mobile parity y polish

| Fase | Nombre                         | Estado | PR  |
| ---- | ------------------------------ | ------ | --- |
| 9.1  | Web sidebar como drawer mobile | ✅     | —   |
| 9.2  | Análisis screen en mobile      | ✅     | —   |

### Fase 10 — Soft-delete + papelera de transacciones

| Fase | Nombre                                | Estado | PR  |
| ---- | ------------------------------------- | ------ | --- |
| 10.1 | Backend soft-delete + endpoints trash | ✅     | —   |
| 10.2 | Web papelera + capa shared            | ✅     | —   |
| 10.3 | Mobile papelera                       | ✅     | —   |

### Fase 11 — Infra y polish

| Fase | Nombre                                  | Estado | PR  |
| ---- | --------------------------------------- | ------ | --- |
| 11.1 | Cron nocturno de tasas (APScheduler)    | ✅     | —   |
| 11.2 | Currency store cross-platform           | ✅     | —   |
| 11.3 | Sistema de toasts global                | ✅     | —   |
| 11.4 | Polish flujo captura mobile (toasts)    | ✅     | —   |
| 11.5 | Imports + receipts confirm web a toasts | ✅     | —   |
| 11.6 | Test setup mobile (`jest-expo`)         | ✅     | —   |

### Fase 12 — Presupuestos por categoría

| Fase | Nombre                                | Estado | PR  |
| ---- | ------------------------------------- | ------ | --- |
| 12.1 | Backend (modelo + endpoints + status) | ✅     | —   |
| 12.2 | Frontend web (ruta + form + lista)    | ✅     | —   |
| 12.3 | Frontend mobile (pantalla)            | ✅     | —   |

### Fase 13 — Detección de subscripciones recurrentes

| Fase | Nombre                               | Estado | PR  |
| ---- | ------------------------------------ | ------ | --- |
| 13.1 | Backend (modelo + heurística + cron) | ✅     | —   |
| 13.2 | Frontend web                         | ✅     | —   |
| 13.3 | Frontend mobile                      | ✅     | —   |

### Fase 14 — Polish y refinamiento

| Fase | Nombre                                       | Estado | PR  |
| ---- | -------------------------------------------- | ------ | --- |
| 14.1 | Edición inline amount presupuestos           | ✅     | —   |
| 14.2 | Sección "Descartadas" en subscriptions UI    | ✅     | —   |
| 14.3 | Date picker nativo mobile                    | ✅     | —   |
| 14.4 | `convertAll` toggle en mobile                | ✅     | —   |
| 14.5 | Notificaciones proactivas budget over        | ✅     | —   |
| 14.6 | Cobertura UI mobile                          | ✅     | —   |
| 14.7 | Detector subscripciones — fusión por prefijo | ✅     | —   |

### Fase 15 — Polish ronda 2

| Fase | Nombre                             | Estado | PR  |
| ---- | ---------------------------------- | ------ | --- |
| 15.1 | Dedup de toasts repetidos          | ✅     | —   |
| 15.2 | Pause / cancel para subscripciones | ✅     | —   |

### Fase 16 — Cross-currency budgets

| Fase | Nombre                                 | Estado | PR  |
| ---- | -------------------------------------- | ------ | --- |
| 16   | Opt-in flag `convert_other_currencies` | ✅     | —   |

### Fase 17 — Gastos fijos (rename + autoposting)

| Fase | Nombre                                    | Estado | PR  |
| ---- | ----------------------------------------- | ------ | --- |
| 17.1 | Rename `subscriptions` → `fixed_expenses` | ✅     | —   |
| 17.2 | Auto-post de gastos fijos confirmados     | ✅     | —   |
| 17.3 | Reconciliación de imports con `expected`  | ✅     | —   |

### Fase 18 — Charting library

| Fase | Nombre                                       | Estado | PR  |
| ---- | -------------------------------------------- | ------ | --- |
| 18.1 | Web — Recharts (balance + i/e + donut)       | ✅     | —   |
| 18.2 | Mobile — react-native-gifted-charts (polish) | ✅     | —   |

### Fase 19 — Bank mappings (auto-aprendizaje en imports)

| Fase | Nombre                                          | Estado | PR  |
| ---- | ----------------------------------------------- | ------ | --- |
| 19   | Bank-concept ↔ category mappings con auto-learn | ✅     | —   |

### Fase 20 — Rules engine + seed bancos españoles + AI suggest

| Fase | Nombre                                            | Estado | PR  |
| ---- | ------------------------------------------------- | ------ | --- |
| 20   | Rules engine + seed (~30 reglas) + Ollama suggest | ✅     | —   |

### Fase 21 — Cuentas, transferencias internas y patrimonio

| Fase | Nombre                                                  | Estado | PR  |
| ---- | ------------------------------------------------------- | ------ | --- |
| 21.1 | Categorías color/icon + presets cross-platform          | ✅     | —   |
| 21.2 | Accounts module + onboarding + account_id obligatorio   | ✅     | —   |
| 21.3 | Transfers + matcher + saldos + filtro cuenta + balances | ✅     | —   |

### Fase 22 — Módulo de deuda

| Fase | Nombre                                                 | Estado | PR  |
| ---- | ------------------------------------------------------ | ------ | --- |
| 22   | Liabilities + amortización francesa + KPIs salud deuda | ✅     | —   |

### Fase 23 — Transferencias internas: flag + convertir desde tx

| Fase | Nombre                                                                      | Estado | PR  |
| ---- | --------------------------------------------------------------------------- | ------ | --- |
| 23   | Tercer kind transfer + UI sospechosas en /transfers                         | ✅     | —   |
| 23.1 | `Category.is_transfer` flag + convertir tx a transferencia + cuenta destino | ✅     | —   |

### Fase 24 — Operaciones financiadas (deuda con plan de pago)

| Fase | Nombre                                                                                    | Estado | PR  |
| ---- | ----------------------------------------------------------------------------------------- | ------ | --- |
| 24   | Convertir tx en operación financiada + crear liability al vuelo + badge en import preview | ✅     | —   |
| 24.1 | Cuotas persistidas editables + marcar pagada                                              | ✅     | —   |
| 24.2 | TIN + TAE separados + tarjetas financiadas con plan fijo                                  | ✅     | —   |
| 24.3 | Total a pagar (banco) + cargos derivados dinámicamente                                    | ✅     | —   |

### Fase 25 — Drill-down de categoría desde el desglose

| Fase | Nombre                                                          | Estado | PR  |
| ---- | --------------------------------------------------------------- | ------ | --- |
| 25   | Página de detalle al pinchar una categoría + "Otros" expandible | ✅     | —   |

### Fase 26 — Imports hardening (XLSX smart + capital obligatorio + errores PDF)

| Fase | Nombre                                                                                                                                 | Estado | PR  |
| ---- | -------------------------------------------------------------------------------------------------------------------------------------- | ------ | --- |
| 26   | Parser XLSX inteligente (auto-roles) + tolerancia a cabeceras desplazadas + capital obligatorio en loan/mortgage + mensajes PDF claros | ✅     | —   |

### Fase 27 — Selector temporal + filtros sincronizados con URL

| Fase | Nombre                                                                                                                        | Estado | PR  |
| ---- | ----------------------------------------------------------------------------------------------------------------------------- | ------ | --- |
| 27   | TimeSelector reutilizable (años + meses sólo con datos) en transacciones y drill-down de categoría + filtros viajan en la URL | ✅     | —   |

### Fase 28 — Transferencias con cuenta ordenante / beneficiaria explícita

| Fase | Nombre                                                                                                                                       | Estado | PR  |
| ---- | -------------------------------------------------------------------------------------------------------------------------------------------- | ------ | --- |
| 28   | Modal con dos slots (ordenante/beneficiaria) + fuerza categoría canónica al kind correcto (fix de la dirección inferida desde category.kind) | ✅     | —   |

### Fase 29 — Refactor visual Análisis + chrome global (copper brand)

| Fase | Nombre                                                                   | Estado | PR  |
| ---- | ------------------------------------------------------------------------ | ------ | --- |
| 29.1 | Copper brand tokens (azul → cobre alineado con el logo)                  | ✅     | —   |
| 29.2 | Sidebar refactor (items grandes + ico-wraps + CTA gradient)              | ✅     | —   |
| 29.3 | Header chrome (bell+dot, currency pill, user chip, divisores)            | ✅     | —   |
| 29.4 | Section tabs con iconos + count badges + underline copper                | ✅     | —   |
| 29.5 | PositionHero (fusión BalancesCard + DebtHealthCard) en /analysis         | ✅     | —   |
| 29.6 | Polish cards (donut hover-center, sparkline, centered bar, tooltip Neto) | ✅     | —   |

### Fase 30 — Rediseño módulo deuda en dos capas

Planificación + ADR + wireframe en
[`phases/README.md`](phases/README.md) (plan ejecutivo conjunto con
PHASE-31), [`decisions/0003-debt-module-two-layer-architecture.md`](decisions/0003-debt-module-two-layer-architecture.md)
y [`design-explorations/debt-redesign-30/wireframe.md`](design-explorations/debt-redesign-30/wireframe.md).

| Fase | Nombre                                                                                                          | Estado | PR  |
| ---- | --------------------------------------------------------------------------------------------------------------- | ------ | --- |
| 30.1 | Enum `categories.role` + migración backfill desde `is_transfer`                                                 | ✅     | —   |
| 30.2 | Endpoint `/debt/category-summary` + bandas BdE 30/35% + fix `time_to_payoff`                                    | ✅     | —   |
| 30.3 | Web: rediseño `/debt` con Capa 1 hero                                                                           | ✅     | —   |
| 30.4 | Web: Capa 2 condensada + vinculación contrato-categoría                                                         | ✅     | —   |
| 30.5 | Mobile parity                                                                                                   | ✅     | —   |
| 30.6 | Selector de divisa del header propagado a los 3 endpoints de deuda                                              | ✅     | —   |
| 30.7 | Selector temporal `month/quarter/year` (alineado con `StitchPeriodToggle`) + donut por tipo de cuenta vinculada | ✅     | —   |
| 30.8 | Navegador de período (Capa 1) con flechas acotadas a datos + KPIs period-scoped                                 | ✅     | —   |
| 30.9 | Serie diaria del saldo de deuda (`range=month`) + chart combo emisión/amortización                              | ✅     | —   |

### Fase 31 — Saneamiento de cuentas e integridad de saldos

| Fase | Nombre                                                                                           | Estado | PR  |
| ---- | ------------------------------------------------------------------------------------------------ | ------ | --- |
| 31.1 | Seed bidireccional de transferencias + categoría INCOME + migración con backfill                 | ✅     | —   |
| 31.2 | UI bulk-fix: detección y corrección de transferencias con dirección dudosa                       | ✅     | —   |
| 31.3 | `else_=0` para tx sin categoría + banner UX                                                      | ✅     | —   |
| 31.4 | Brokerage/crypto fuera del patrimonio neto agregado                                              | ✅     | —   |
| 31.5 | `_infer_transfer_kind` robustecido (no asume EXPENSE arbitrario, respeta categoría preexistente) | ✅     | —   |

> Pre-requisito completado antes de PHASE-30. Hotfix SQL aplicado al
> usuario `membrij7@gmail.com` (~7 tx, ~€11.7k recategorizadas) durante
> la implementación.

### Fase 32 — Cuenta principal, reasignación e integridad de transferencias

| Fase | Nombre                                                                                                                                                                                                              | Estado | PR  |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | --- |
| 32   | `accounts.is_default` (cuenta principal = ahorro neto, pre-seleccionada) + `POST /transactions/reassign-account` (consolidar mes) + fix dirección de transferencias en imports + invalidación debt al mutar cuentas | ✅     | —   |

> Detalle en [`phases/phase-32-default-account-and-transfer-direction.md`](phases/phase-32-default-account-and-transfer-direction.md).
> Código completo y verde (FE + 445 tests BE); en `main` (commit `5a5fc74`,
> 2026-06-26).

### Fase 33 — Transferencias internas: overhaul de UX e integridad

| Fase | Nombre                                                                                                                                                                                                                                                                                                                              | Estado | PR  |
| ---- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | --- |
| 33   | Overhaul transversal (web + móvil) en 8 entregas: detección ES (BIZUM/TRASPASO) en sospechosas + badge de 3 estados (par/huérfana/deuda) + grupo "Transferencias" en el combobox + canal "A revisar" separado de "Errores" en imports + lenguaje cotidiano + dirección explícita en móvil + guard 409 al editar una pata emparejada | ✅     | —   |

> Detalle en [`phases/phase-33-transfers-ux.md`](phases/phase-33-transfers-ux.md).
> Código completo y verde (FE: 67 web + 18 móvil · BE: 560 tests · ruff +
> mypy); en `main` (commits transfers-ux P1–P8, `8ae798e`…`5527f61`, 2026-06-26).

### Fase 34 — La verdad del dinero vive en la transacción (`flow`)

| Fase | Nombre                                                                                                                                                                                                                                                                                                                                                                                                                                 | Estado | PR  |
| ---- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | --- |
| 34   | Columna `transactions.flow` (IN/OUT/TRANSFER\_\*) como fuente de verdad del dinero (ADR-0004): saldo + cashflow derivan de `flow`+`account.nature`, no de la categoría. Import y forms escriben `flow` (signo del extracto = invariante duro); `classify_import_flow` detecta transferencias y pago/liquidación de tarjeta; absorción del "cargo espejo" del `ADEUDO`; "Cuadrar saldo" + recategorización en bloque; saldo = caja real | ✅     | —   |

> Detalle en [`phases/phase-34-transaction-flow.md`](phases/phase-34-transaction-flow.md)
> y [`decisions/0004-transaction-level-money-truth.md`](decisions/0004-transaction-level-money-truth.md).
> Código completo y verde (BE: 589 tests · ruff · mypy · FE: 71 web + 18
> móvil · typecheck · lint). Cierra la familia de lecciones PHASE-23.1/28/32.
> En `main` (squash `5215a80`, 2026-07-04, junto con PHASE-35 y PHASE-36).

### Fase 35 — Compras a plazos bajo una tarjeta (`parent_account_id`)

| Fase | Nombre                                                                                                                                                                                                                                                                            | Estado | PR  |
| ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | --- |
| 35   | `accounts.parent_account_id`: una tarjeta agrupa varias compras financiadas a plazos, cada una con su cuadro propio. FE: alta de compra a plazos bajo una tarjeta + agrupación padre→hijas con total combinado en `/debt` + ocultar hijas de los selectores de transacción/import | ✅     | —   |

> Detalle en [`phases/phase-35-installment-cards.md`](phases/phase-35-installment-cards.md).
> Convive con PHASE-34 en la misma rama. Backend + frontend completos y
> verdes. En `main` (squash `5215a80`, 2026-07-04, junto con PHASE-34 y PHASE-36).

### Fase 36 — Saldo de deuda gobernado por el cuadro + reconciliación

| Fase | Nombre                                                                                                                                                                                                                                                                                                                                                                                                                                                         | Estado | PR  |
| ---- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | --- |
| 36   | El saldo vivo de una liability con plan sale de las cuotas no pagadas del cuadro (`schedule_outstanding`); `POST /accounts/reconcile-debt` marca pagadas las cuotas desde los movimientos reales del extracto (amortización de préstamo FIFO + cargo agregado de tarjeta financiada), sin patas sintéticas ni tocar el cashflow. Ancla temporal para cuotas previas a los datos, exceso como `assumed_unregistered_debt`. Idempotente + reversible (`dry_run`) | ✅     | —   |

> Detalle en [`phases/phase-36-schedule-driven-debt-reconciliation.md`](phases/phase-36-schedule-driven-debt-reconciliation.md).
> En `main` (squash `5215a80`, 2026-07-04, `Refs: PHASE-34, PHASE-35, PHASE-36`).
> Documentada retroactivamente (la fase se plegó en el squash sin doc propia).

### Fase 37 — Rediseño módulo Análisis + saneamiento de deuda

| Fase | Nombre                                                                                                            | Estado | PR  |
| ---- | ----------------------------------------------------------------------------------------------------------------- | ------ | --- |
| 37.1 | Serie temporal de patrimonio + `signed_amount_expr` + Δ-periodo                                                   | ✅     | —   |
| 37.2 | KPI strip + grid ancho + cuentas colapsables + donut top-6                                                        | ✅     | —   |
| 37.3 | Gasto estructural vs puntual + tasa de ahorro dual (`is_exceptional`)                                             | ✅     | —   |
| —    | Bugfix: autoaprendizaje no fija categoría para concepto de dirección ambigua (BIZUM)                              | ✅     | —   |
| —    | Deuda: interés y deuda viva desde el cuadro de amortización (MUX por pasivo)                                      | ✅     | —   |
| 37.4 | Proyección fin de mes + runway (`/analytics/month-outlook`)                                                       | ✅     | —   |
| 37.5 | Smart Insights v2 (no-redundancia + insights derivados)                                                           | ✅     | —   |
| 37.6 | Mobile parity (month-outlook + insights v2 + filtro estructural donut + composición deuda + evolución patrimonio) | ✅     | —   |

> Detalle en [`phases/phase-37-analysis-redesign.md`](phases/phase-37-analysis-redesign.md)
> (as-built) y [`phase-37-analysis-redesign.md`](phase-37-analysis-redesign.md) (plan).
> **En `main`** (push directo, fast-forward hasta `89eea70`, 2026-07-12; sin PR).
> 643 tests BE + 95 web + 18 móvil · mypy · ruff · lint · typecheck verdes.

### Fase 38 — Cuota de compra a plazos = gasto de caja + estandarización de layout web

Solo web + backend (sin paridad móvil). No hay migraciones ni endpoints nuevos.

| Fase | Nombre                                                                                                                                                                                            | Estado | PR  |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | --- |
| 38.1 | Carve-out `is_card_financed_op` en `classify_import_flow`: la CUOTA de una compra a plazos con tarjeta cuenta como gasto real (`flow=OUT`); ADEUDO/liquidación y creación de deuda siguen neutros | ✅     | —   |
| 38.2 | UX deuda-como-gasto: el form fija el segmento Gasto/Ingreso desde `category.kind` + badge "Pago de deuda" (`role=DEBT_PAYMENT/DEBT_INTEREST`) en la lista                                         | ✅     | —   |
| 38.3 | Estandarización layout web: tokens `layout.{pageWide,pageNarrow}` + `Card`/`CardTitle`/`CardHeader` (padding `lg` por defecto, `compact` opt-in) en ~22 páginas y 5 cards                         | ✅     | —   |
| —    | Housekeeping: `type: ignore[attr-defined]` en `rowcount` (auth + transactions repos) · poda de backlog                                                                                            | ✅     | —   |

> Detalle en [`phases/phase-38-installment-cash-expense-and-web-layout.md`](phases/phase-38-installment-cash-expense-and-web-layout.md).
> Cierra la familia de lecciones PHASE-34/37/38 sobre "qué es un pago de deuda".
> **En `main`** (commit `ac3b456`, push directo `89eea70`, 2026-07-12; sin PR).
> Sin paridad móvil todavía y sin prueba manual previa al merge (follow-ups).

### Fase 39 — Saldo del extracto como ancla del saldo real

| Fase | Nombre                                                                                                                                                                                                                                                                                                                   | Estado | PR  |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------ | --- |
| 39   | Columna Saldo del extracto capturada por fila (`transactions.statement_balance`) + auto-anclaje del `opening_balance` al confirmar imports (misma semántica que "Cuadrar saldo", a fecha del extracto) + `accounts.anchored_statement_balance` para re-derivar al importar historia vieja + UI (mapping, preview, toast) | ✅     | —   |

> Detalle en [`phases/phase-39-statement-balance-anchor.md`](phases/phase-39-statement-balance-anchor.md).
> En `main` (commit `1a35bbf`). La prueba manual de reimportación sigue
> pendiente; el código lleva commiteado desde entonces. Origen:
> auditoría de integridad [`audits/2026-07-13-data-integrity-pending-check.md`](audits/2026-07-13-data-integrity-pending-check.md).

### Fase 40 — Flag `counts_as_debt` (tarjeta revolving fuera de deuda)

| Fase | Nombre                                                                                                                                                                                                                                                                                                 | Estado | PR  |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------ | --- |
| 40   | `accounts.counts_as_debt` (default true): una tarjeta pagada íntegra cada mes se excluye del módulo de deuda (deuda viva, DTI, composición, historia, movimientos) pero se mantiene en el patrimonio neto. Backend (columna + migración + debt_health/history/service) + FE (tipo + toggle en el form) | ✅     | —   |

> Sin doc de fase propia (documentada inline). En `main` (commit `5c1d01c`,
> junto con PHASE-41, 2026-07-15).

### Fase 41 — Simplificación del módulo Finanzas Domésticas

| Fase | Nombre                                                                                                                                                                                                                                                                                                                                                                                                          | Estado | PR  |
| ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | --- |
| 41   | Retirada de la pestaña Transferencias + maquinaria de emparejado heurístico (ADR-0005 T4) · papelera atómica del par (borrar arrastra la pareja, restaurar re-vincula) · tickets heredan auto-categoría + `flow=OUT` · `MisclassifiedSection` movido a Transacciones. Conserva load-bearing (`link`/`unlink`, `from-source`/`-debt`). NO se fusionaron los motores de recurrencia (falso positivo del análisis) | ✅     | —   |

> Detalle en [`phases/phase-41-module-simplification.md`](phases/phase-41-module-simplification.md).
> Origen: análisis de utilidad financiera de las pestañas. En `main` (commits
> `5c1d01c`…`9c9f47f`, push directo, 2026-07-15). BE 668 tests · mypy · ruff ·
> FE typecheck · lint · web 101 + móvil 18.

### Fase 42 — Rango de fechas personalizado (fuera trimestral)

| Fase | Nombre                                                                                                                                                                                                                                                                                                                                                                                                       | Estado | PR  |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------ | --- |
| 42   | Fuera `quarter`; dentro rango libre `custom` (from/to) end-to-end (Análisis + Dashboard + Deuda, web + móvil) · backend `date_from/date_to` en `by-month` y `debt/category-summary` (day-exact, bordes parciales) + nuevo `GET /accounts/position-as-of` · consistencia: Ingresos vs Gastos = totales del periodo, patrimonio a fecha de fin de rango, chart de patrimonio respeta el toggle "incluir deuda" | ✅     | —   |

> Detalle en [`phases/phase-42-custom-date-range.md`](phases/phase-42-custom-date-range.md).
> En `main` (commits `209b31a` · `c22fc94` · `693fad0`, push directo,
> 2026-07-16). BE 673 tests · mypy · ruff · FE typecheck · lint · web 106 +
> móvil 18. Datos del periodo validados al céntimo contra `transactions`.
> Follow-up: paridad móvil de "Ingresos vs Gastos" (totales de periodo).

### Fase 43 — Split dashboard/análisis (ADR-0006) + saneamiento

| Fase | Nombre                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | Estado | PR  |
| ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | --- |
| 43   | Dashboard = balance/stocks (patrimonio + tarjetas de módulo: veredicto + número + link), Análisis = cuenta de resultados/flujos (ADR-0006) · `expense_nature` (estructural vs puntual) + recurrencia + smart insights v2 · patrimonio con pasivos dirigidos por el cuadro (un préstamo amortiza en el neto y cuadra con Deuda / `get_balances`) · tarjeta Deuda del dashboard period-scoped · `debt_movement_bounds` sólo cuenta cuotas pagadas (el navegador no cae en meses sin datos) · guardarraíles de calendario (re-clamp del ancla, rango acotado a días con datos, popover que voltea en el borde) · poda de código muerto (knip ~2.3k LoC + vulture) cableada a `make verify` | ✅     | —   |

> Plan en [`improvements/phase-43-dashboard-analysis-split.md`](improvements/phase-43-dashboard-analysis-split.md)
> y ADR [`decisions/0006-balance-vs-income-statement.md`](decisions/0006-balance-vs-income-statement.md).
> En `main` (commits `1f987dd` · `99da1a7` · `31a5a70` · `fb91f45`, push directo,
> 2026-07-19). BE 696 tests · mypy · ruff · knip · FE typecheck · lint.
> Sin paridad móvil (sólo web + backend). Follow-up: la línea "Pasivos" del chart
> de evolución sigue a 12 meses fijos (no responde al selector de período).

### Fase 44 — Módulo de Inversión (green-field)

Módulo nuevo desacoplado (cartera + análisis fundamental forense). Diseño en
[`improvements/DESIGN-v2-investment-module.md`](improvements/DESIGN-v2-investment-module.md)
y [`improvements/ARCHITECTURE-investment-module.md`](improvements/ARCHITECTURE-investment-module.md).

| Fase  | Nombre                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | Estado                     | PR  |
| ----- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------- | --- |
| 44.1  | Cimientos: 8 enums nativos + 13 tablas (catálogo/fundamentales/umbrales/precios globales · cartera/análisis scoped) + migración reversible (`alembic check` verde) + ADR-0007 tablas globales + tests de modelo                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | ✅                         | —   |
| 44.2  | Engine puro Capa 1: `CanonicalStatement` (48 partidas) + convenciones §4.5 (media t/t−1, guardas, hueco ≠ 0) + 17 derivaciones §4.4 + 27 métricas base con bandas + DuPont + banderas `ebt_divergence`/`fcf_divergence`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | ✅                         | —   |
| 44.3  | Engine capas 1.5 y 2: evolutiva (E1 horizontal · E2 common-size · E3 σ de márgenes · E4 crecimiento sostenible · cruces C1-C8) + forense (M-Score, Z'', F-Score, accruals, F5, F6, FZ, F7 con desglose) + catálogo agregado de 37 métricas                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | ✅                         | —   |
| 44.4  | Engine Capa 3 (dividendo): cobertura D1-D8 · calidad de caja Q1-Q5 (Q4 anomalía fiscal) · soporte de balance B1-B4 (B4 dividendo financiado con deuda) · trayectoria T1-T4 · ajuste REIT sobre FFO · helpers `population_stdev`/`cagr` compartidos · catálogo agregado de 51 métricas                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | ✅                         | —   |
| 44.5  | Engine capas 3.5 y 4 (**cierra el engine**): stress paramétrico (ST1 shock de ingresos · ST2 shock de tipos · ST3 breakeven) + síntesis (4 preguntas con semáforo por regla · matriz Conservador/Vigilar/Evitar · `dividend_verdict` · confianza = completitud × frescura · matriz de banderas)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | ✅                         | —   |
| 44.6  | Adapter EDGAR — **cruzado + ingesta pura + adapter**. `pretax_income` entra como partida canónica 49; el `concept_map` pasa del script al módulo con sus 4 mecanismos (candidatos · combinación · `dei` · signo) + normalización + cuadres; y el adapter monta `edgartools==5.43.0` pineada con reparto explícito: la librería identifica y parsea, nosotros guardamos el crudo y anclamos los hechos al ejercicio por fecha de cierre. Falta persistencia (`IngestionJob`, endpoints) y la prueba en vivo                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | ✅                         | —   |
| 44.7  | **Módulo completo (BE + web + móvil) en un solo commit.** Persistencia + API (catálogo/fundamentales/análisis/cartera/precios) sobre las 13 tablas de 44.1 (cero migraciones) · ingesta síncrona por job · seed de umbrales (1440 filas) + hash · builder BD→engine + serializador JSONB + `AnalysisRun` · golden con MCD/O/JNJ reales · FIFO + acciones corporativas (split/stock_dividend) + dividendos · `PriceAdapter`/Finnhub (sin key → desactivado) + `/portfolio/summary` · web (Tab Análisis + Cartera, registro `enabled`, `AccountsGuard` eximido) · móvil (shell + tabs + veredicto)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | ✅                         | —   |
| 44.10 | **Las métricas que el cuaderno pedía.** DuPont extendido de 5 factores con la identidad que CIERRA —usa el EBIT reportado en el margen operativo y en el coste financiero; con el limpio arriba y el reportado abajo el ROE reconstruido salía inflado hasta 4 puntos porcentuales en JNJ 2023, en silencio y sólo en los años con deterioros— más sus dos filas de comprobación · `S7` endeudamiento (banda 1-2, `applies=False` en financieras) y `S8` calidad de la deuda · tres piezas del motor que nadie llamaba (caja libre de mantenimiento, circulante operativo y fondo de maniobra) cableadas como series de la evolutiva. 57 métricas, motor 1.2.0, sin migración                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 | ✅                         | —   |
| 44.9  | **Informe de análisis con pestañas.** Backend: el catálogo de métricas y las 49 partidas viajan por API con etiqueta y unidad · `analysis_runs.thresholds_used` persiste los cortes efectivos (eran irrecuperables: el seed muta la fila in situ y el hash es irreversible) · `QuestionVerdict.signals[]` con valor, banda y motivo de las que no puntúan — antes 8 señales eran la clave en crudo y una financiera pintaba verde por ausencia de prueba sin poder detectarse · `runs/latest` (el informe moría al recargar) · `DUPONT_EM` catalogada (52 métricas) · gate de `ENGINE_VERSION` que se afirmaba desde 44.2 y no existía. Web: hero persistente + 6 pestañas en la URL (Estados · Ratios · Evolución · Forense · Dividendo · Veredicto), matriz métrica × ejercicio multi-año, formato por unidad (un margen ya no se lee «0,42») y el perfil como checklist auditable. Retirados los 4 componentes viejos                                                                                                                                                                                                                                                                                                                      | ✅                         | —   |
| 44.8  | Buscador de valores **local-first** (ADR-0008). E1: el servidor decide la plaza (`venues.py`; un país no es un mercado) e identidad por `(cik, ticker)` — el cliente mandaba `exchange:'US'` y duplicaba filas · regla única de analizabilidad con motivo (`capabilities.py`) respaldada por evidencia contada en la SEC y persistida en `securities.analysis_status` (MCD 33 10-K → `ok`; SPY 0/0 → `no_annual`; SAN 0 10-K + 25 20-F → `non_gaap`) · 500→404, 422 con motivo, debounce 250 ms con suelo de 2 caracteres y aviso, key de búsqueda fuera de `investment.all` · fuera `PriceAdapter.symbol_search`. **E2 en PHASE-44.13**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | 🚧 E1+E2                   | —   |
| 44.11 | **Precios vivos y valoración en euros.** Adapter `yfinance` pineado (primario, multi-mercado, sin credencial) tras selector `PRICE_PROVIDER`; Finnhub convive. El `PriceAdapter` pasa a lote quotes-only y **la divisa la declara el proveedor**, no el catálogo — antes se persistía la del catálogo junto a un precio de fuera, y un valor de Londres en peniques etiquetado como libras vale 100 veces más. FX sin piezas nuevas: `exchange_rates` vía `currency` ([ADR-0009](decisions/0009-single-fx-source-currency-transversal.md)), con `fx_as_of` efectivo por posición y exclusión estándar cuando falta tasa (`convert` devuelve el importe SIN convertir, no un error). Corregido un **dato ficticio**: `fx_rate_at_trade` tenía `default=1`, inocuo mientras `fx_effect` salía 0 y falso en cuanto se cableó el FX real — ahora se deriva del BCE a la fecha de compra                                                                                                                                                                                                                                                                                                                                                           | 🚧 pendiente prueba manual | —   |
| 44.20 | **Paridad móvil real.** La capa compartida cubría **57 de 64**: las otras siete (`DUPONT_OM/TAX/FIN`, `E3`, `E4`, `T2`, `T3`) estaban escritas a mano en tres ficheros de web, así que móvil —que renderiza estrictamente desde el fichero compartido— no las pintaba nunca. Tres secciones nuevas con filas tipadas (el DuPont lleva una comprobación que **no** es una métrica) + `dupontCheckRow` sube a `@crisol/ui`. Móvil gana el DuPont entero, las dos métricas de Evolución —esa pestaña no pintaba ninguna— y la Trayectoria, incluido el dividendo por acción año a año. Y un **gate en el backend** —donde están las 64 y donde CI sí corre— que falla si una métrica del motor no tiene sitio en pantalla. El test de paridad que debía cazarlo era **ciego**: comparaba contra la lista compartida, que es justo donde faltaba el DuPont                                                                                                                                                                                                                                                                                                                                                                                        | 🚧 pendiente prueba manual | —   |
| 44.19 | **Las métricas que un gate escondía.** `dividend_verdict='not_applicable'` colapsa dos situaciones (`synthesis.py:520`): una financiera —aunque reparta— y una empresa que no reparte. La pestaña se ocultaba entera con esa etiqueta y con ella **ocho métricas ya calculadas, con valor y banda**, incluidas las cuatro de calidad de la caja, que no dependen del dividendo. Ahora se decide contra el RUN (`dps_series`, no la fila viva) y cada caso enseña lo que sobrevive. Antes de destapar hubo que arreglar el motor: no tenía guarda para financieras y habría pintado D2-D5 y **D8** —que también divide por caja libre, pese a su nombre— con banda y color. Latente: no hay ninguna financiera en el catálogo                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | 🚧 pendiente prueba manual | —   |
| 44.18 | **La banda que no llega.** Dos cortes independientes, uno en cada extremo. `seed_if_empty` se rendía en cuanto la tabla tenía una fila, así que toda métrica añadida después quedaba fuera **para siempre**: 1440 filas, **40 sembradas frente a 42 con banda** (S7 y S8, de 44.10, nunca entraron). Y en el otro extremo `effectiveThreshold` descartaba `applies` y `model_variant`, los dos únicos atributos por los que la tabla se diferencia del catálogo. Entremedias, una exención **razonada, documentada e inerte**: la de S7 en financieras dependía de una fila que no existía, así que se muda al engine, donde no puede perderse. Sembrado sólo-inserción (un reseed mutante rompería la reproducibilidad que 44.9 compró)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | 🚧 pendiente prueba manual | —   |
| 44.16 | **El informe tolera análisis de motores anteriores.** Un `AnalysisRun` es JSONB persistido: la tabla guarda runs de TODAS las versiones del motor, pero los tipos describían sólo la que produce el de hoy —seis campos obligatorios que un run de 1.0.0 no tiene—, así que `tsc` no podía avisar de ninguno de los **ocho** accesos inseguros. Pulsar una pregunta en MCD (único valor analizado antes de 44.9) reventaba con `signals.length` sobre `undefined`. Pero el crash era lo de menos: la misma ausencia hacía que el cuadre del DuPont pintara **«NaN» en rojo** denunciando «un problema en los datos o en una fórmula» —un descuadre contable inexistente en cuentas reales— y que seis métricas que el motor no emitía se anunciaran «no calculable con los datos disponibles», culpando a los balances de la empresa. Tipos honestos (el compilador enumera los ocho), tri-estado compartido `questionEvidence`, regla 7 de honestidad en `metricRow` y `StaleRunNotice` comparando versiones. Fixture extraída de la BD real; todas las regresiones validadas reintroduciendo el bug                                                                                                                                         | 🚧 pendiente prueba manual | —   |
| 44.15 | **Entregas 3 y 4 del buscador (cierra PHASE-44.8) y cuatro deudas.** El combobox pasa a serlo de verdad: `role="combobox"` con nombre accesible, teclado completo (↑↓ Enter Esc) y `aria-activedescendant`, más la prop `intent` — en Análisis, SPY sale `aria-disabled` **con el motivo pintado** (no en un `title`, que en táctil no existe) porque elegirlo lleva al callejón de «lanza la ingesta» que acaba de fallar; en Cartera es válido. E4: la pantalla de Cartera de móvil era de sólo lectura y decía «añádelas desde la web» — ahora tiene el alta, con coma decimal y **sin** campo de tipo de cambio (lo deriva el servidor; pedirlo invitaría al `1` ficticio que costó el lote de JNJ). Deuda: `accounting_std` deja de ser un literal `GAAP` y se **deriva de la evidencia** —la mina que llevaba tres fases con un «arréglalo quien toque `ANNUAL_FORMS`»—, el ranking devuelve la matriz primero (`santander`→SAN, y de regalo `johnson`→JNJ), `pandas`/`lxml` se declaran, y las 14 tablas del módulo entran por fin en `schema.md`                                                                                                                                                                                      | 🚧 pendiente prueba manual | —   |
| 44.14 | **Directorio oficial UE/UK (FIRDS) + alta validada** — la Entrega 5 del buscador, y la mitad que faltaba del multi-mercado: cotizar un valor de Madrid existía desde 44.11, pero **no había forma de crearlo**, así que el mapa de sufijos estaba varado. [ADR-0010](decisions/0010-identity-official-registers.md): identidad **sólo** sobre registros oficiales (EDGAR + ESMA + FCA, locales tras seed), precios sobre capas tolerantes; Twelve Data descartada (su licencia prohíbe cachear y el uso comercial). Tabla `listing_directory` + `pg_trgm`, parser FULINS en streaming (809 MB el fichero de la FCA), seed idempotente de **3.012 filas** en 12 mercados, y alta `ext:` validada: identidad de FIRDS, resolución ISIN→símbolo con **bypass manual** cuando falla, cross-check sufijo↔plaza y cotización real antes de persistir. Tres hallazgos doblaron el plan: FIRDS reporta en MICs de **segmento** (Allianz está en `XETA`, nunca en `XETR` → sin normalizar, Alemania entera fuera), los tablones alemanes cotizan el mundo entero (Frankfurt sola: 12.298 filas), y el fichero de la FCA trae venues europeos — lo cazó el **dry-run** con un choque de PK. El aviso «ITX → Inditex» desaparece: Inditex sale de verdad | 🚧 pendiente prueba manual | —   |
| 44.13 | **Buscador E2, paridad móvil del informe y el cron de tasas que llevaba mudo desde PHASE-11.1.** Tres frentes: (a) el cron nocturno de divisas no traía **nada** desde que se construyó —canario que acepta cualquier tasa de 14 días atrás **y** timeout de 10 s cuando una fecha histórica tarda 13-17—; huella en la BD: una fecha cada ~15 días. Política estricta compartida con la cartera, que ya se la había inventado para sí. (b) Buscador E2: índice en memoria de los **10.365 emisores** de la SEC, sin red, con colapso por CIK (Santander salía 3 veces), subcadena acotada por longitud (`ITX` casaba con `ADITXT`) y fuzzy sobre tokens (`Macdonald`→MCD); identidad por `listing_key` opaca + `POST /adopt`, que conserva la plaza que `/resolve` perdía. (c) Paridad móvil de las 6 pestañas moviendo la capa PURA a `packages/ui` —formato, filas, banderas y **qué métricas por bloque**— en vez de duplicarla: el móvil pintaba las señales en crudo y los márgenes como `0,42`                                                                                                                                                                                                                                         | 🚧 pendiente prueba manual | —   |
| 44.27 | **Primero lo que está MAL, luego lo que se explica mal, y sólo entonces lo que falta.** Plan que recoge DOS auditorías del mismo día. La de calibración cierra la duda del usuario sobre el dividendo de MCD: el rojo está **sobredeterminado por tres mecanismos** —`B3`, `FZ` y el escenario de stress— así que **no existe ninguna forma de aflojar el bloque que cambie el badge**, y el veredicto es «correcto como color, defectuoso como explicación: no se toca ni un corte». La de cobertura cruza las 57 métricas del cuaderno `Check-metrics.md` contra las 65 del motor (30 respondidas, 11 alcanzables, 15 imposibles porque viven en la prosa del MD&A). Y por el camino aparece lo que no preguntaba nadie: `DepreciationDepletionAndAmortization` es un valor **PARCIAL** en MCD —457 M$ frente a 2.199— así que la deuda neta/EBITDA sale 3,17 en vez de 2,79 y en 2022 quedó **a ocho centésimas** de pintar sobreendeudamiento, contaminando cinco métricas en silencio y marcada como dato auditado. El testigo que lo prueba estaba en la misma fila: una amortización sola no puede ser menor que la depreciación sola | ⏳ plan, sin código | — |
| 44.26 | **El Dictamen se lee de arriba abajo.** La card de 44.25 era técnicamente honesta y humanamente ilegible — feedback literal: «apuntes técnicos que hacen inviable su entendimiento de forma rápida». El diagnóstico del workflow: problema de JERARQUÍA, no de prosa — las frases legibles ya las componía el servidor y estaban enterradas bajo la matriz de reglas. Orden nuevo en las DOS apps desde la misma capa: las cuatro preguntas primero, «Qué preocupa» (rojas primero, con distancia y enlace; el tope `max(6, rojas)` **jamás esconde una roja**), «Qué está bien (sólo lo comprobado)» —un verde sin evidencia o bajo una pregunta sin auditar NO es una fortaleza, y en una financiera el predicado permanentemente-no-auditable de `next_checks` se espeja UNA vez para las dos listas—, el contrafactual, y la matriz entera **plegada** como «La auditoría del sello» (abierta y sin control en el dictamen imprimible). Cero plantillas nuevas: `NARRATIVE_VERSION` sigue en 1.1.0 y el backend no se toca. Una sonda que no mordía destapó que el caso del test no llegaba a la guarda — se reescribió con el caso real | 🚧 pendiente prueba manual | — |
| 44.25 | **El veredicto argumenta su porqué.** El informe demostraba todo y no argumentaba nada: el titular culpaba al «X-Score en rojo» y ninguna fila decía que esa fila y esa frase eran la misma cosa, con un Z''-Score en **verde** justo al lado que nadie conciliaba. El motor SÍ lo sabía —evalúa la banda con el `MetricResult` en la mano— y tiraba la precisión al serializar: `blocking_reasons` es prosa sin claves. Peor: en «Evitar» retornaba **antes** de evaluar las seis condiciones de «Conservador», así que «qué haría falta para salir» no existía como dato — y la pantalla lo rellenaba infiriendo de cadenas, afirmando que se cumplían condiciones que **nadie había comprobado** («F-Score ≥ 7 ✓» salía siempre) con un glifo bimodal que negaba la única línea que respondía a la pregunta. Motor **1.8.0**: `SAFETY_MATRIX` junto a la fórmula, las diez condiciones evaluadas y persistidas con sus señales, `met` **tri-estado** y `blocking_reasons` derivado **byte-igual** (golden de equivalencia). La presentación ensambla el porqué al servir —`why` es **`None`** para un run viejo: precondición, no etiqueta—, marca la señal que decidió (**decisiva ≠ roja**: el stress tiñe su pregunta sin estar en la matriz) y rellena la fila más hueca con las frases del escenario que **ya estaban persistidas**. La evidencia se cuenta por bandas: «0 se comprobaron y salieron limpias» se leía como «las 8 salieron mal» cuando 6 estaban en verde. Y móvil salda la paridad de `SignalList` prometida en 44.24.C y nunca entregada | 🚧 pendiente prueba manual | — |
| 44.24 | **El informe demuestra todo y explica poco.** Siete entregas. **A**: `what/why/reading` para las 64 métricas, las 8 fichas de score con sus **27 variables** —la tarjeta imprimía `DSRI` y `P4_cfo_supera_beneficio` en crudo— y las 20 banderas con **dónde comprobarlas en las cuentas**, que es lo que las separa de un oráculo. **M** (motor **1.7.0**): `ThresholdSpec.origin` persistido, porque derivar la vara comparando contra el catálogo de HOY etiqueta como sectorial un run genérico; y la señal de stress de una financiera deja de puntuar. **C**: `presentation/` puro con **distancia al corte**, orden por severidad y procedencia — el semáforo era binario y «a un pelo» se veía igual que «lejísimos». **B**: las frases del veredicto se componen en el SERVIDOR, con las plantillas como DATO (hasheables y escaneables) y 17 goldens de texto exacto. **D**: nivel **y dirección** — un Z'' de 2,6 que viene de 3,1 cuenta otra historia; columna de tendencia en las 5 matrices de las 2 apps y móvil gana el desglose de scores, que **no tenía ninguno**. **E**: las marcas estaban definidas en **tres** sitios con títulos ya divergentes y **tres de las cinco** pestañas no pintaban leyenda; más la guía «Cómo leer este informe» y la paridad móvil del veredicto entero. **F**: comparador de runs, donde `comparable` es **precondición** y no etiqueta — con el motor cambiado NO se emite ni un cambio de empresa. **G**: dictamen imprimible (no había ninguna regla `@media print` en la app) | 🚧 pendiente prueba manual | — |
| 44.23 | **Qué es cada fila del informe.** El informe pinta **64 métricas y 49 partidas** con su valor, su unidad y su banda, y la única pista de qué eran era la etiqueta — que no basta: «Prueba ácida» y «Ratio de caja» son cosas distintas, y hay decisiones del motor que sólo se sabían leyendo el código (varios ratios usan la media de dos ejercicios; S4 parte del EBIT **reportado** mientras S2 y S4b usan el limpio; «Total pasivo» a menudo no viene en el filing y se deduce restando, y entonces el cuadre se cumple por construcción). Las 113 definiciones viven en el **engine, junto a la fórmula** —escribirlas en la pantalla es el mecanismo exacto que dejó tres rótulos mintiendo en 44.9, y una definición miente más fácil porque nadie la contrasta— y viajan por el mismo catálogo que la etiqueta. Cuatro gates: cobertura en las **dos** direcciones (falta / huérfana), no tautológica, y **ningún umbral escrito a mano** (las bandas se calibran por sector desde 44.21; un corte en prosa caduca en silencio). Afordance: `ⓘ` que despliega bajo la fila en web —no un `title`, que el teclado no abre y que se recorta en un contenedor con scroll— y **tocar la etiqueta** en móvil, donde no hay hover          | 🚧 pendiente prueba manual | —   |
| 44.22 | **Los tres charts del informe.** Lo único grande que quedaba en tablas: heatmap de variaciones (magnitud × ejercicio), deriva de la estructura de márgenes y dumbbell de los escenarios de stress con la línea del 1,0. El color se **calculó**: la escala verde↔rojo tiene los polos a ΔE 2,6 bajo protanopía, así que el valor con su signo va impreso en cada celda —el color es refuerzo, nunca la fuente—, y la paleta de la deriva empezó siendo dos cobres que el validador tumbó a ΔE 14,3 **con visión normal**. Un test cazó de paso que la escala tenía tres bandas y dos cortes: el paso más claro de cada rampa era inalcanzable. Sólo web                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | 🚧 pendiente prueba manual | —   |
| 44.21 | **La vara depende del negocio: calibración sectorial.** Doce perfiles de deltas sobre la banda genérica, con la aplicabilidad en el **engine** y no sólo en la tabla — que es lo que dejó la exención de S7 inerte ocho fases. Una eléctrica con deuda neta 4,8× sale ámbar (mediana de grado de inversión del sector 5,1×) y una tecnológica con 2,5×, roja: el perfil no es «relajar». Un banco ve apagadas las 33 métricas que no describen su negocio, **cada una con su motivo**, y re-bandeadas las tres que sí (ROA en banda bancaria, ROE, patrimonio/activo como proxy de capital, declarado como proxy). Dos reglas cruzadas: un retail que cobra antes de pagar deja de salir en rojo de liquidez, y una regulada con payout alto recibe la pregunta que decide —quién financia el exceso—. Y las **cuatro preguntas declaran sus portantes**: sin uno, la pregunta sale _no auditada_ (el cuarto estado, gris) en vez de verde. No es una proporción a propósito: un ratio trataría igual una señal cualquiera que el M-Score. Motor **1.6.0**                                                                                                                                                                                    | 🚧 pendiente prueba manual | —   |
| 44.17 | **Lo que no se pudo medir, se dice.** El motivo de un hueco era el del ejercicio MÁS ANTIGUO —en McDonald's, «sin ejercicio 2020», que invitaba a ingerir historia que no arregla nada—, la leyenda del forense estaba escrita a mano y era falsa en los cinco ejercicios, y no tener deuda venciendo a doce meses salía como «denominador cero», indistinguible de un dato ausente: la empresa perdía una señal de resiliencia **por tenerlo todo pagado**. Después, lo que el plan tenía bloqueado: las reglas de bandera publican **si se pudieron evaluar**, porque una que aborta por falta de un dato y una comprobada y limpia producían la misma ausencia y la síntesis las traducía a «no se ha encendido». Default pesimista **con gate de cobertura** —sin él, el falso verde se convierte en un falso gris universal—, rachas consecutivas en vez de cardinales, y el tercer modo de ausencia (el cero imputado) separado del dato que falta. Motor **1.4.0** y **1.5.0**                                                                                                                                                                                                                                                         | 🚧 pendiente prueba manual | —   |
| 44.12 | **Múltiplos de valoración** (la «hoja 10» del cuaderno). Capa PURA `engine/valuation.py` con 7 métricas —PER, precio/ventas, precio/valor contable, precio/caja libre, EV/EBITDA + valor contable por acción y rentabilidad de la caja libre— que cruzan la cotización viva con el último ejercicio. **Fuera del `AnalysisRun`**: un múltiplo se mueve con el precio y el run tiene que poder reejecutarse dando lo mismo, así que se calcula al vuelo y la UI lo separa del veredicto («¿es seguro?» y «¿está cara?» son preguntas distintas). Ninguna lleva banda: sin comparables de sector, un semáforo sería una opinión disfrazada de dato. Capitalización única para los cinco (`precio × shares_outstanding_eop`), guard de denominador ≤ 0, valor de empresa ≤ 0 interceptado antes de dividir, doble staleness visible y semáforo del proveedor de 3 estados. Motor **1.3.0**, 64 métricas catalogadas y 42 con umbral                                                                                                                                                                                                                                                                                                              | 🚧 pendiente prueba manual | —   |

> Plan de 44.27 en [`improvements/phase-44.27-data-integrity-and-metric-coverage.md`](improvements/phase-44.27-data-integrity-and-metric-coverage.md),
> con las **dos decisiones de producto ya cerradas por el usuario** —el escenario
> de stress y `B3` dejan de puntuar, porque _una hipótesis informa pero no
> dictamina_ y _una métrica ciega a las líneas de crédito no puede decidir sola_—,
> la especificación de implementación con el mecanismo real (`counted=False` +
> `outcome="informational"`, que **no** es como son display-only `D1` y `D8`), y la
> lista explícita de **lo que NO hay que hacer**: los cinco atajos de calibración y
> las siete propuestas del cuaderno que chocan con el diseño. Nada de esto empieza
> antes de la prueba manual de 44.24/44.25/44.26.

> Detalle de 44.26 en [`phases/phase-44.26-dictamen-reads-top-down.md`](phases/phase-44.26-dictamen-reads-top-down.md).
> Renegocia el invariante «un sello sin sus reglas no es auditable»: la matriz
> no desaparece, se ABRE — y los tests que la clavaban visible pasan a abrirla,
> que es el gesto del usuario.

> Detalle de 44.25 en [`phases/phase-44.25-verdict-argues-its-why.md`](phases/phase-44.25-verdict-argues-its-why.md)
> y el plan, con el diagnóstico citado línea a línea, en
> [`improvements/phase-44.25-verdict-argues-its-why.md`](improvements/phase-44.25-verdict-argues-its-why.md).
> Origen: la prueba manual del usuario sobre MCD — «no se entiende el porqué
> exactamente se debería evitar». Abre una familia de lecciones nueva: **una
> pantalla que no puede afirmar un dato lo DICE en vez de inferirlo**, y su
> corolario, que la inferencia por cadenas no sólo era frágil sino que
> **afirmaba comprobaciones que el motor no había hecho**.

> Detalle de 44.24 en sus CINCO documentos de fase —
> [A](phases/phase-44.24.A-meaning-layer.md) ·
> [M](phases/phase-44.24.M-threshold-origin.md) ·
> [C](phases/phase-44.24.C-signal-gradient.md) ·
> [D](phases/phase-44.24.D-level-and-direction.md) ·
> [E/F/G](phases/phase-44.24.EFG-guide-comparison-print.md) ·
> [H](phases/phase-44.24.H-ux-audit-fixes.md) (la auditoría UX que abrió la prueba manual:
> **33 defectos reales**, entre ellos veintiuna señales del veredicto que enlazaban a la
> misma pestaña y la prosa de las cards a 2.400 px) — y el plan completo, con
> las siete entregas, sus decisiones y el registro de la revisión adversarial en
> [el plan](improvements/phase-44.24-report-legibility-implementation-plan.md).
> La fase abre tres familias de lecciones nuevas: **una definición vive junto a
> la fórmula** (no en la pantalla que la pinta), **una sonda que no muerde
> significa que hay otro camino al verde** —pasó cuatro veces— y **presentar
> juntos un cambio de la empresa y uno del método es peor que no comparar**.

> Detalle de 44.22 en [`phases/phase-44.22-report-charts.md`](phases/phase-44.22-report-charts.md),
> de 44.17 en [`phases/phase-44.17-honest-absences.md`](phases/phase-44.17-honest-absences.md)
> y de 44.21 en [`phases/phase-44.21-sector-calibration.md`](phases/phase-44.21-sector-calibration.md),
> con su calibración en [`improvements/sector-calibration-investment.md`](improvements/sector-calibration-investment.md).
> Las dos cierran a la vez dos familias de lecciones: la del **gate que mira a
> otro lado** —la huella del motor comparaba nombres de campo, así que un estado
> nuevo en un `Literal` no la movía— y la de la **premisa razonada sin test**, que
> se revierte sola: apagar S8 en financieras lo cazó un test escrito en 44.10 con
> su motivo dentro.

> Detalle de 44.16 en [`phases/phase-44.16-legacy-run-tolerance.md`](phases/phase-44.16-legacy-run-tolerance.md),
> de 44.15 en [`phases/phase-44.15-search-e3-e4-and-debt.md`](phases/phase-44.15-search-e3-e4-and-debt.md)
> y de 44.14 en [`phases/phase-44.14-eu-uk-listing-directory.md`](phases/phase-44.14-eu-uk-listing-directory.md).
> 44.16 sale de un fallo reportado en la app viva («sólo en McDonald's… me lleva a un 404»)
> y cierra la familia de lecciones sobre premisas escritas a mano que caducan, con un
> mecanismo nuevo: **un documento persistido es la unión de todas las versiones que has
> escrito**, así que el tipo que describe sólo la última apaga al compilador justo donde
> más falta hace.

> Detalle de 44.9 en [`phases/phase-44.9-analysis-report-contract.md`](phases/phase-44.9-analysis-report-contract.md)
> y plan completo (wireframes, criterios de aceptación) en
> [`improvements/phase-44.9-investment-analysis-report.md`](improvements/phase-44.9-investment-analysis-report.md).
> Origen: la pantalla pintaba 22 de 52 métricas, de un solo ejercicio, moría al
> recargar (vivía en una mutación) y **tres etiquetas mentían sobre su propio
> número** (F5, F6, D8) — el mecanismo de [PHASE-43] «una premisa escrita a mano
> caduca en silencio». Verde: BE **1106 tests** (409 de inversión) · ruff · black
> · mypy 212 · `alembic upgrade/downgrade` reversibles, cabeza única, sin drift ·
> FE typecheck · lint · knip · **133 tests web** + 18 móvil. La valoración por
> múltiplos del cuaderno del usuario **no entra** (el engine no recibe precio por
> diseño) y se declara en pantalla; los umbrales del cuaderno vs. los del motor
> quedan en [`investment-threshold-divergences.md`](investment-threshold-divergences.md).
> **Pendiente**: prueba manual del usuario y paridad móvil.

> Detalle y checkpoint de 44.6 en [`phases/phase-44.6-edgar-crosscheck-WIP.md`](phases/phase-44.6-edgar-crosscheck-WIP.md).
> Decisiones cerradas por el usuario: EBIT derivado del pretax + intereses ·
> `total_liabilities = activo − patrimonio` · REIT con liquidez/COGS
> `not_computable` apoyado en FFO/D6 · `pretax_income` como partida 49.
> Verde: ruff · black · mypy 174 · BE **984 passed** (suite completa) + los 34
> tests del adapter re-ejecutados tras el último refactor · `alembic
upgrade/downgrade` reversibles · `alembic check` sin drift. Las dos
> derivaciones inutilizan la comprobación que tendría esa partida como testigo,
> así que `ebt_divergence` no se evalúa con el EBIT derivado y el cuadre de
> balance se informa como **no verificable** — nunca como superado.
>
> **Cerrado y en `origin/main` el 2026-07-26** (commit `140725d`, junto con
> PHASE-44.8 E1). El smoke en vivo contra MCD/O/JNJ se ejecutó y cazó el bug del
> `getattr` sobre un método (ver `lessons.md`); el análisis de MCD se ha
> verificado a mano en la web.

> Detalle en [`phases/phase-44.1-investment-foundations.md`](phases/phase-44.1-investment-foundations.md)
> y ADR [`decisions/0007-investment-global-tables.md`](decisions/0007-investment-global-tables.md).
> Código completo y verde (BE: ruff · black · mypy 152 · `alembic upgrade/downgrade`
> reversibles · `alembic check` sin drift · 11 tests de modelo + 693 suite completa).
> Sin endpoints ni UI todavía. Seed de `scoring_thresholds` diferido a 44.2
> (confirmado por el usuario 2026-07-20).

> Detalle de 44.2 en [`phases/phase-44.2-investment-engine-base.md`](phases/phase-44.2-investment-engine-base.md).
> Engine PURO (sin BD/red/reloj, con test de pureza por AST). Código completo y
> verde (ruff · black · mypy 159 · 71 tests en 4,0 s). `METRIC_CATALOG` es la
> fuente única de las `metric_key`, lo que cierra el riesgo de drift del seed.
> El recuento 27 y la política ausencia-vs-cero (`imputed_zero`) quedaron
> cerrados en la revisión de documentos del 2026-07-20.

> Detalle de 44.3 en [`phases/phase-44.3-investment-engine-evolution-forensic.md`](phases/phase-44.3-investment-engine-evolution-forensic.md).
> Capas 1.5 + 2 completas y verdes (ruff · black · mypy 163 · 45 tests nuevos ·
> 116 del engine en 6,3 s · suite BE **809 passed**). `catalog.py` agrega las 37
> métricas de las tres capas — fuente única para el seed. Regla dura verificada:
> en financieras los 8 scores forenses salen `not_computable` con razón, nunca
> omitidos. Follow-ups en [`backlog.md`](backlog.md#módulo-inversión--follow-ups-fase-44).

> Detalle de 44.4 en [`phases/phase-44.4-investment-engine-dividend.md`](phases/phase-44.4-investment-engine-dividend.md).
> Capa 3 (dividendo) completa y verde (ruff · black · mypy 164 · 35 tests nuevos ·
> 162 del módulo en 8,6 s). El catálogo agrega ya 51 métricas. Quedan las capas
> 3.5 (stress) y 4 (síntesis) para cerrar el engine.

> Detalle de 44.5 en [`phases/phase-44.5-investment-engine-stress-synthesis.md`](phases/phase-44.5-investment-engine-stress-synthesis.md).
> **Engine COMPLETO** (6 capas puras). Capas 3.5 + 4 verdes (ruff · black · mypy
> 166 · 26 tests nuevos · 188 del módulo en 9,8 s). La síntesis recibe los
> resultados ya calculados de cada capa (resuelve la inyección de bandas para
> B1/B2). Lo siguiente sale del engine: el adapter EDGAR (44.6), con parada para
> el cruzado con empresas reales.

### Fase 45 — «Es una amortización»: el cargo del banco que baja la deuda

| Fase | Nombre                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | Estado                     | PR  |
| ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------- | --- |
| 45   | Un `ADEUDO MENSUAL DE TARJETA` sacaba el dinero de la cuenta y **no tocaba el módulo de deuda**: no había gesto para decir «esto paga esta deuda». Panel nuevo (web + móvil) con previsualizador contra el servidor. Cómo baja la deuda lo decide el pasivo —con cuadro se marcan cuotas y baja por el **capital**, no por lo pagado; sin cuadro se crea la contrapartida y baja entera—; si cuenta como **gasto** lo declara el usuario, con la sugerencia razonada al lado (una tarjeta cuyas compras ya están en la app no puede cobrarlas dos veces). Columna `transactions.amortization_source_id` en vez de reutilizar `transfer_pair_id`: emparejar una pata declarada como gasto la borraría de presupuestos y del gasto de deuda, que filtran `transfer_pair_id IS NULL` | 🚧 pendiente prueba manual | —   |

### Fase 46 — La deuda que nace no es un ingreso

| Fase | Nombre                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | Estado                     | PR  |
| ---- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------- | --- |
| 46   | Julio de 2026 tenía **700,26 € de ingreso que nadie cobró** — el 100 % del ingreso del mes— y 700,26 € de gasto que doblaba compras ya contadas. BBVA financió el recibo de la tarjeta con dos redacciones que ninguna lista conocía (`Recibo anterior … Otras financiaciones` / `Recibo mes anterior`); el **mismo hecho en marzo**, escrito `Operacion financiada`, se había clasificado bien. Las liquidaciones de tarjeta se declaraban por duplicado —servicio y repositorio— y divergieron: el clasificador la contó como gasto **y** el buscador del cargo espejo no la reconoció. Ahora la secuencia se declara una vez y cada consumidor deriva su forma (subcadena / `ILIKE`), con un gate que falla si vuelven a separarse. La financiación entrante nunca es ingreso, **condicionada al signo** — el mismo producto es gasto real cuando llega la cuota—, y a qué deuda pertenece lo decide el **capital del cuadro**, no el texto: el usuario ya había creado el pasivo con los 700,26 € exactos y sólo faltaba el enlace. La prueba manual añadió lo que faltaba: ese extracto viene **sin signos**, así que una fila que no diga «abono» ni resuelva categoría entra sin dirección — pero PHASE-39 ya guardaba el **saldo del extracto** en esa misma fila, y el salto (717,10 → 1.417,36) la prueba. Segunda pasada que rellena la dirección con el salto, exigiendo coincidencia exacta y respetando el orden del extracto. Y destapó que el problema era mayor: el extracto de la **tarjeta** se había importado a la cuenta del **banco** (julio: 0 compras en la tarjeta frente a 7 en mayo y 7 en junio) | 🚧 pendiente reimportación | —   |

> Detalle en [`phases/phase-46-financing-is-not-income.md`](phases/phase-46-financing-is-not-income.md).
> Sin migraciones. Verde: BE 1353 tests · ruff · black · mypy · FE typecheck ·
> lint · knip · 307 tests. Los tests nuevos verificados **rompiendo el código**.

> Detalle en [`phases/phase-45-amortization-link.md`](phases/phase-45-amortization-link.md).
> El MUX de PHASE-36 («el cuadro manda») se extrae a `resolve_liability_outstanding`
> para que el saldo que promete el panel y el que enseña el módulo de deuda no
> puedan divergir, y el greedy de cuotas pasa a ser una función PURA compartida
> por el previsualizador y el aplicador. Verde: 19 tests nuevos de backend
> **verificados rompiendo el código** (bajar por lo pagado en vez de por el
> capital, y emparejar siempre, tumban tres), 9 de la capa compartida y 7 del
> panel web (también verificado rompiéndolo).

### Fase 47 — Recomposición de deuda: bandeja, detalle por deuda y costura

Plan en [`improvements/phase-47-implementation-plan.md`](improvements/phase-47-implementation-plan.md)
(que manda sobre el [anexo](improvements/phase-47-anexo-implementacion.md) y el
[plan original](improvements/phase-47-debt-recomposition-inbox.md)) ·
[ADR-0011](decisions/0011-system-initiated-debt-event-translation.md).

| Fase | Nombre                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | Estado                                                               | PR  |
| ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- | --- |
| 47.A | **Cimientos, sin comportamiento nuevo salvo un portero.** Los seis módulos de deuda se mudan de `accounts/` a `debt/` con sus 13 schemas y cero migraciones, con un golden byte a byte de `debt-health`/`balances`/`category-summary` tomado ANTES del movimiento y un test de capas por AST que impide que el ciclo vuelva (las URLs `/accounts/debt-*` no se tocan: cambiarlas rompe contrato). `accounts.settlement_account_id` crea el dato que no existía —qué cuenta de activo cobra cada pasivo—, sin el cual no se puede saber qué cargo cierra el ciclo de qué tarjeta: en julio había **4 cargos y 6 pasivos**. No se adivina, se **propone** contando los cargos que el usuario ya enlazó en PHASE-45, en sus dos formas, callando ante un empate y sin escribirse sola. Y el guardarraíl del import, que es el agujero por el que entró el lío: la huella de la cabecera caza un fichero con el formato de otra cuenta —la única señal que habría cazado julio— y el solape de dedup cruzado caza una reimportación. Avisos **bloqueables**: el botón se apaga hasta el tick y el commit responde 409 sin él. Una revisión adversarial posterior destapó que esa huella salía de las **claves del parser**, fijas por contrato: era la misma constante para todo PDF y todo XLSX, así que F.1 estaba ciega justo en el caso de julio y la suite en verde no lo veía. Corregido —la cabecera real viaja aparte desde el parser— con los dos tests que faltaban                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | 🚧 pendiente prueba manual (parada A)                                | —   |
| 47.B | La bandeja + detalle por deuda                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | ⏳ bloqueada por la parada 2 (mes verde de mayo/junio + calibración) | —   |
| 47.C | Flujo unificado, retirada de los seis diálogos y paridad móvil                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | ⏳                                                                   | —   |
| 47.E | **El recibo aplazado: el gasto existe, pero no ha salido.** Frente aparte, abierto a mitad de fase cuando el usuario destapó el descuadre de raíz: importa el extracto de la tarjeta para controlar su gasto, así que las 17 compras de junio ya estaban contadas una a una — y al financiar el recibo la app **sumaba deuda sin restar nada**. Ahora una marca por compra (`deferred_by_account_id`) sostiene **dos lecturas**: el resultado del mes las excluye (mide caja: ese dinero no salió) y el desglose por categorías las mantiene (mide gasto: la compra se hizo), con la diferencia dicha en voz alta — porque a partir de aquí las dos cifras no cuadran **a propósito**. El ciclo se **deriva** (las últimas compras que suman EXACTO el recibo) y si no cierra al céntimo no se marca nada: el recibo de 990,02 € no cierra porque faltan compras de mayo, y decirlo es mejor que aproximar. Más: un recibo que BBVA escribe con dos redacciones y hasta 5 días de desfase deja de entrar 2-4 veces (~20 filas borradas a mano en siete meses) **sin** comerse el par de financiación, que tiene exactamente la misma forma y es el hecho contrario; y el cargo agregado de la tarjeta alcanza por fin al recibo aplazado, lo que de paso destapó que **dos pasivos de tipo préstamo vuelven ambiguo el cargo de amortización** y el préstamo real deja de amortizar en silencio. **E4 (23-ago)**: el aviso decía CUÁNTO hay aplazado pero no DÓNDE — con nueve categorías en pantalla, 496,67 € no señalan ninguna fila. `deferred_total` por categoría en los dos endpoints del desglose, asterisco en la fila (con el importe escrito al lado en móvil, donde no hay hover) y el aviso **derivado de lo que se muestra**: al medirlo apareció que bajo el filtro Fijo citaba 496,67 € cuando en pantalla sólo había 245,53 € de ellos. Retirada de paso la copia palabra por palabra de `deriveStructural` en las dos apps, que es como habrían divergido | 🚧 pendiente prueba manual                                           | —   |

| 47.F | **El dinero prestado es dinero.** El saldo de BBVA salía **700,26 € por debajo** del que imprime el banco. Ese abono entró de verdad —el saldo del propio extracto subió de 717,10 a 1.417,36— pero la app aplicaba **dos** correcciones al mismo hecho: anulaba el abono en el saldo _y_ borraba el cargo que lo compensaba. Con las dos el neto salía 0; en julio la segunda se comió una línea que venía del extracto de la **tarjeta** importado por error en el banco, y la primera se quedó sin pareja. La justificación escrita del carve-out estaba **invertida** —caja +X contra deuda +X deja el patrimonio igual; caja 0 contra deuda +X lo deja en −X, así que la app apuntaba la deuda y escondía el dinero—. Ahora cada línea del extracto aporta su propio signo, emparejar cambia **qué es** el movimiento y no hacia dónde fue, y convertir a deuda deja de mover el saldo (el ancla deja de caducar sola). Más: la financiación entrante mira la **dirección** y no el signo crudo, que un extracto de tarjeta no trae. Y `audit_balances_vs_statement`, que compara cada saldo con el testigo que PHASE-39 guardaba desde entonces sin que nadie lo consultara | 🚧 pendiente arreglo de datos + prueba manual | — |

| 47.G | **El extracto manda, y la app desconfía sola.** Seis devoluciones entraron como GASTO entre abril y julio (238,87 €, o sea 477,74 € de desvío: el doble de error que perderlas). Dos capas: `_parse_amount_signed` sólo llama «entrada» a un `+` explícito, así que un `33,58 €` desnudo caía en la categoría —que para un Amazon dice «compras»—; **la convención de signos es del FICHERO, no de la fila**, y ese fichero escribe los cargos en negativo. Y la que importa: la comprobación por saldo existía pero sólo tocaba las filas SIN dirección, así que una conjetura que acertaba a decidir —mal— nunca se contrastaba. Ahora la **cadena de saldos MANDA** sobre la conjetura. Más: `statement_gap` por cuenta (el testigo de PHASE-39 llevaba tres fases guardándose sin que nadie lo leyera), `find_statement_seams` —que reporta los 1.211,95 € que faltan entre el 30-jun y el 5-jul—, el aviso en la pantalla de cuentas y `make audit-balances`. Cierra la familia de nueve lecciones «la dirección se decidió con algo que describe en vez de con algo que demuestra» | 🚧 pendiente prueba manual | — |

| 47.H | **Una devolución no es un ingreso.** Julio mostraba **2.664,23 € de ingresos con una nómina de 2.520,68** — las tres devoluciones de Amazon que 47.G acababa de corregir de dirección entraban en el cubo de ingresos. El neto era correcto; mentía el reparto, y con él la tasa de ahorro, el runway y el **DTI de deuda**, que divide por los ingresos. Una devolución es una entrada (`flow=IN`, dirección probada contra el extracto) en categoría de GASTO: resta de su propia categoría. El signo vive en un helper **explícito** aplicado a los **7 sitios que suman** (de 26 usos del predicado) y NO en la expresión de importe compartida, que usan 39 sitios entre ellos los saldos — firmar allí habría movido el saldo. Propiedad verificada en todos los periodos: **el neto no se mueve**. Presupuestos fuera por decisión del usuario. **Segunda entrega (23-ago)**: el signo llega a la pantalla. El item del ranking viajaba SIN dirección —el importe es el que ordena—, así que «Suscripciones» de julio enseñaba seis movimientos que sumaban 187,95 € bajo un total de 184,95 €: dos cifras plausibles que sólo se contradicen si las miras juntas. `TopExpenseItem.flow` en los dos endpoints que lo emiten, un gemelo puro de `expense_amount_expr` compartido por las listas de las dos apps, el campo **opcional** en el tipo porque un backend anterior no lo manda, y un gate de cableado — porque `formatAmount(tx.amount)` compila hoy y compilará siempre. Una revisión adversarial (4/4 lentes, 8 hallazgos confirmados de 26) destapó el **tercer emisor**: `top_exceptional` de analytics filtra por el MISMO `_is_expense()` y «Top movimientos del periodo» pintaba el importe crudo, contradiciendo al desglose de la misma pantalla — con los datos reales el corte del top-5 de junio está en 43,58 € y la devolución de ese mes es de 41,35 €. Y que el gate v1 comprobaba PRESENCIA y no efecto: cuatro esquivas normales, ejecutadas, daban verde | 🚧 pendiente prueba manual | — |

| 47.I | **Una declaración manual sobrevive a una reimportación.** El 18-ago el usuario reimportó julio y la reimportación borró las filas viejas creando otras: con ellas se fueron los cuatro `Adeudo mensual` que había declarado GASTO (1.099,64 €), y **el resultado del mes pasó de −253,17 a +398,87 € sin que nadie lo decidiera**. La fila nueva llega con el MISMO `import_hash`, así que la anterior es localizable en la papelera; lo que no lo era es qué de ella era decisión y qué conjetura del clasificador — las dos viven en `flow` y ninguna iba firmada. `transactions.flow_declared_at` es esa firma, y el import repone lo declarado diciéndolo en el resumen. Un bloqueante casi lo tumba: el hash se calculaba sobre `occurred_at.isoformat()`, así que el arreglo de 47.J habría matado los ~557 hashes persistidos; serializar la fecha SIN el sufijo de zona reproduce byte a byte lo que producía el naive. Más: el cargo agregado de tarjeta deja de avanzar una cuota de TODAS las tarjetas —con dos, la deuda bajaba el doble de lo pagado— usando `settlement_account_id`, que existía desde 47.A sin lector, y callando cuando no puede decidir | 🚧 pendiente prueba manual | — |

| 47.J | **Una fecha de extracto es una fecha CIVIL.** «13/02/2026» se persistía como `2026-02-12T23:00:00Z`: el parser devolvía un naive y asyncpg lo interpreta en la zona DEL PROCESO, así que el dato dependía del ordenador que hizo el import y de la estación del año. **469 de 491 filas desplazadas un día y 14 de mes** —una transferencia de 4.267,47 € contando en marzo siendo del 1 de abril—, con la firma en los datos: 276 filas a las 22:00 UTC y 193 a las 23:00, las dos medianoches de Madrid. Invisible cuatro fases porque la pantalla formatea en local y sólo asoma en los BORDES; lo destapó el ciclo con corte el 13. Parser anclado en UTC + tipo `CivilDatetime` en los schemas de entrada + `formatCivilDate` y `toDateInputValue` leyendo en UTC (éste **escribía**: en huso negativo habría restado un día en cada guardado). Datos corregidos con el `import_hash` como TESTIGO: 548 filas y 10 cuotas, 557/557 hashes siguen válidos y los saldos no se movieron | 🚧 pendiente prueba manual | — |

> Detalle de 47.I en [`phases/phase-47.I-declarations-survive-reimport.md`](phases/phase-47.I-declarations-survive-reimport.md)
> y de 47.J en [`phases/phase-47.J-a-statement-date-is-a-civil-date.md`](phases/phase-47.J-a-statement-date-is-a-civil-date.md).

### Fase 48 — El mes lo define el usuario

| Fase | Nombre                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | Estado                     | PR  |
| ---- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------- | --- |
| 48   | **El día en que cobras REDEFINE qué es un mes.** Se construyó primero como PRESET —un chip «Mi ciclo» junto a «Mes»— y el usuario lo probó: _«sigue siendo raro e incómodo… que se cambie todo directamente»_. Tenía razón y la causa era de diseño: el día de cobro no es una vista, es la respuesta a «¿qué es un mes para ti?», y ofrecer las dos a la vez obliga a mantenerlas sincronizadas — no lo estaban, sólo CINCO endpoints entendían el ciclo. Ahora el chip desaparece de las dos familias de UI, «Mes» es su mes, el período se llama por el mes que lo ABRE, y **el año también se desplaza** (12-ene → 11-ene), esto último porque el usuario vio el bucket «Dic 25» que hacía falta sin ello: _«si estoy viendo gastos de 2026, no debería salir ese diciembre de 2025»_. Seis agregados del backend que derivaban su propio mes pasan a cortar por el suyo. El método fue la mitad de la entrega: borrar `cycle` del TIPO primero y dejar que el compilador dictara los ~35 puntos — de paso destapó tres defectos vivos. Una revisión adversarial encontró nueve más, **cinco introducidos en este mismo trabajo**, ninguno visible con la suite en verde | 🚧 pendiente prueba manual | —   |

> Detalle en [`phases/phase-48-the-user-defines-the-month.md`](phases/phase-48-the-user-defines-the-month.md).
> El plan original ([`improvements/user-defined-month-cycle-implementation-plan.md`](improvements/user-defined-month-cycle-implementation-plan.md))
> lleva un aviso de re-alcance al principio: su cuerpo describe el diseño de
> preset que el usuario rechazó, y sin ese aviso alguien lo reconstruiría.

> Detalle de 47.H en [`phases/phase-47.H-a-refund-is-not-income.md`](phases/phase-47.H-a-refund-is-not-income.md).

> Detalle de 47.G en [`phases/phase-47.G-the-statement-is-the-authority.md`](phases/phase-47.G-the-statement-is-the-authority.md).
> Sin migraciones. Datos del usuario corregidos con la aritmética del banco fila
> a fila; BBVA cuadra al céntimo y su cadena sólo se rompe donde debe (principio
> de la historia y principio del extracto de julio).

> Detalle de 47.F en [`phases/phase-47.F-borrowed-money-is-money.md`](phases/phase-47.F-borrowed-money-is-money.md).
> Sin migraciones. Verde: BE **1431 tests** · mypy · ruff · black · FE typecheck ·
> lint · knip · 329 tests. El código solo deja BBVA en 3.057,95 € (+1.279,76):
> hay **cuatro** pares de deuda y tres tenían su cargo borrado, así que el
> arreglo de datos no es opcional. La evidencia fila a fila destapó además que
> el extracto de la tarjeta lleva entrando en la cuenta del banco **desde marzo**,
> no sólo en julio.

> Detalle de 47.E en [`phases/phase-47.E-deferred-receipt.md`](phases/phase-47.E-deferred-receipt.md)
> y modelo completo en [`improvements/card-receipt-financing-model.md`](improvements/card-receipt-financing-model.md).
> Decisión del usuario, que gobierna todo lo demás: _«el objetivo del módulo es
> trazar los flujos de caja… son finanzas personales, no empresariales»_ — así
> que la cuota de un préstamo es gasto **íntegra**, no sólo su interés.

> Detalle de 47.A en [`phases/phase-47.A-debt-domain-and-import-guard.md`](phases/phase-47.A-debt-domain-and-import-guard.md).
> Dos migraciones aditivas y reversibles. Todos los tests nuevos **verificados
> rompiendo el código** — y ahí está la lección de la fase: **tres veces** un
> test pasó por la razón equivocada, y las tres se destaparon rompiendo el
> código, nunca releyéndolo. **D5 está respondida** en el plan de
> [PHASE-48](improvements/phase-48-debt-early-settlement.md): los cuatro ADEUDO
> de julio son liquidaciones anticipadas, así que el caso de regresión son items
> `POSSIBLE_SETTLEMENT`, no items de cuota como decía el plan original.

---

## Estructura de este directorio

```
internal_docs/
├── README.md               # este archivo
├── architecture.md         # arquitectura del sistema
├── development-spec.md     # metodología y fases
├── lessons.md              # errores y reglas aprendidas
├── ai-context/             # contexto de consulta bajo demanda para IA
│   └── README.md
├── phases/                 # docs por fase completada
├── decisions/              # ADRs (0001-ui-tokens-only)
├── api/                    # endpoints.md (catálogo)
└── data-model/             # schema.md (estado de las tablas)
```

---

## Cómo usar estos documentos

- **Al empezar una fase**: lee la fase anterior en `phases/` (cuando exista) y
  revisa `lessons.md`.
- **Al terminar una fase**: crea `phases/phase-X.Y-*.md`, actualiza las tablas
  de arriba, y añade lo que corresponda a `api/` y `data-model/`.
- **Al tomar una decisión no trivial**: crea un ADR en `decisions/`.
- **Al corregir un error evitable**: añade una lección a `lessons.md`.
