# Internal Docs — Crisol

Documentación viva del proyecto: arquitectura, metodología, estado por fase,
lecciones aprendidas y contexto de consulta para IA.

A medida que el proyecto avance, esta carpeta crecerá con documentos por fase,
ADRs (Architecture Decision Records), catálogo de endpoints y schema de BD.

## Índice

- [architecture.md](architecture.md) — arquitectura del sistema
- [development-spec.md](development-spec.md) — metodología y fases
- [lessons.md](lessons.md) — errores y reglas aprendidas
- [backlog.md](backlog.md) — deuda técnica, limitaciones y follow-ups
- [api/endpoints.md](api/endpoints.md) — catálogo de endpoints
- [data-model/schema.md](data-model/schema.md) — estado del schema
- [decisions/](decisions/) — ADRs (decisiones arquitectónicas)
- [phases/](phases/) — un documento por fase completada
- [audits/](audits/) — auditorías (seguridad, arquitectura, UX, rendimiento)
- [ai-context/](ai-context/) — contexto de consulta bajo demanda para IA
  (glosario, ejemplos, evaluaciones de modelos, prompts guardados)

---

## Estado de fases

Leyenda: ⏳ pendiente · 🚧 en curso · ✅ completada · ❌ bloqueada

### Fase 0 — Bootstrap

| Fase | Nombre                | Estado | PR |
|------|-----------------------|--------|----|
| 0.0  | Setup inicial (docs)  | ✅     | —  |
| 0.1  | Bootstrap monorepo    | ✅     | #1 |
| 0.2  | Bootstrap backend     | ✅     | —  |
| 0.3  | Bootstrap Ollama      | ✅     | —  |

### Fase 1 — Autenticación

| Fase | Nombre           | Estado | PR |
|------|------------------|--------|----|
| 1.1  | Auth backend     | ✅     | —  |
| 1.2  | Auth frontend    | ✅     | —  |

### Fase 2 — Transacciones

| Fase | Nombre                  | Estado | PR |
|------|-------------------------|--------|----|
| 2.1  | Transactions backend    | ✅     | —  |
| 2.2  | Transactions frontend   | ✅     | —  |

### Fase 3 — Dashboard

| Fase | Nombre              | Estado | PR |
|------|---------------------|--------|----|
| 3.1  | Dashboard backend   | ✅     | —  |
| 3.2  | Dashboard frontend  | ✅     | —  |

### Fase 4 — Importación

| Fase | Nombre             | Estado | PR |
|------|--------------------|--------|----|
| 4.1  | Imports backend    | ✅     | —  |
| 4.2  | Imports frontend   | ✅     | —  |
| 4.3  | PDF imports        | ✅     | —  |

### Fase 5 — IA: tickets

| Fase | Nombre              | Estado | PR |
|------|---------------------|--------|----|
| 5.1  | Receipts backend    | ✅     | —  |
| 5.2  | Receipts frontend   | ✅     | —  |

### Fase 6 — Modularización del frontend

| Fase | Nombre               | Estado | PR |
|------|----------------------|--------|----|
| 6.1  | Module shell + PF    | ✅     | —  |

### Fase 7 — Rediseño dashboard + layout shell

| Fase | Nombre                       | Estado | PR |
|------|------------------------------|--------|----|
| 7.0  | Design primitives + shell    | ✅     | —  |
| 7.1  | Dashboard bento              | ✅     | —  |
| 7.2  | Transactions tabla           | ✅     | —  |
| 7.3  | Imports + Receipts polish    | ✅     | —  |
| 7.4  | Mobile parity                | ✅     | —  |
| 7.5  | Analysis sub-tab             | ✅     | —  |
| 7.6  | Stitch fidelity rewrite      | ✅     | —  |

### Fase 8 — Multimoneda con conversión global

| Fase | Nombre                              | Estado | PR |
|------|-------------------------------------|--------|----|
| 8.1  | Currency rates backend              | ✅     | —  |
| 8.2  | Conversion frontend                 | ✅     | —  |
| 8.3  | Per-transaction conversion in SQL   | ✅     | —  |
| 8.4  | Transactions cross-currency + polish | ✅     | —  |

Plan completo en [phases/phase-8-roadmap.md](phases/phase-8-roadmap.md).

### Fase 9 — Mobile parity y polish

| Fase | Nombre                                | Estado | PR |
|------|---------------------------------------|--------|----|
| 9.1  | Web sidebar como drawer mobile        | ✅     | —  |
| 9.2  | Análisis screen en mobile             | ✅     | —  |

### Fase 10 — Soft-delete + papelera de transacciones

| Fase | Nombre                                | Estado | PR |
|------|---------------------------------------|--------|----|
| 10.1 | Backend soft-delete + endpoints trash | ✅     | —  |
| 10.2 | Web papelera + capa shared            | ✅     | —  |
| 10.3 | Mobile papelera                       | ✅     | —  |

### Fase 11 — Infra y polish

| Fase | Nombre                                | Estado | PR |
|------|---------------------------------------|--------|----|
| 11.1 | Cron nocturno de tasas (APScheduler)  | ✅     | —  |
| 11.2 | Currency store cross-platform         | ✅     | —  |
| 11.3 | Sistema de toasts global              | ✅     | —  |
| 11.4 | Polish flujo captura mobile (toasts)  | ✅     | —  |
| 11.5 | Imports + receipts confirm web a toasts | ✅   | —  |
| 11.6 | Test setup mobile (`jest-expo`)       | ✅     | —  |

### Fase 12 — Presupuestos por categoría

| Fase | Nombre                                | Estado | PR |
|------|---------------------------------------|--------|----|
| 12.1 | Backend (modelo + endpoints + status) | ✅     | —  |
| 12.2 | Frontend web (ruta + form + lista)    | ✅     | —  |
| 12.3 | Frontend mobile (pantalla)            | ✅     | —  |

### Fase 13 — Detección de subscripciones recurrentes

| Fase | Nombre                                 | Estado | PR |
|------|----------------------------------------|--------|----|
| 13.1 | Backend (modelo + heurística + cron)   | ✅     | —  |
| 13.2 | Frontend web                           | ✅     | —  |
| 13.3 | Frontend mobile                        | ✅     | —  |

### Fase 14 — Polish y refinamiento

| Fase | Nombre                                       | Estado | PR |
|------|----------------------------------------------|--------|----|
| 14.1 | Edición inline amount presupuestos           | ✅     | —  |
| 14.2 | Sección "Descartadas" en subscriptions UI    | ✅     | —  |
| 14.3 | Date picker nativo mobile                    | ✅     | —  |
| 14.4 | `convertAll` toggle en mobile                | ✅     | —  |
| 14.5 | Notificaciones proactivas budget over        | ✅     | —  |
| 14.6 | Cobertura UI mobile                          | ✅     | —  |
| 14.7 | Detector subscripciones — fusión por prefijo | ✅     | —  |

### Fase 15 — Polish ronda 2

| Fase | Nombre                                       | Estado | PR |
|------|----------------------------------------------|--------|----|
| 15.1 | Dedup de toasts repetidos                    | ✅     | —  |
| 15.2 | Pause / cancel para subscripciones           | ✅     | —  |

### Fase 16 — Cross-currency budgets

| Fase | Nombre                                       | Estado | PR |
|------|----------------------------------------------|--------|----|
| 16   | Opt-in flag `convert_other_currencies`       | ✅     | —  |

### Fase 17 — Gastos fijos (rename + autoposting)

| Fase | Nombre                                       | Estado | PR |
|------|----------------------------------------------|--------|----|
| 17.1 | Rename `subscriptions` → `fixed_expenses`    | ✅     | —  |
| 17.2 | Auto-post de gastos fijos confirmados        | ✅     | —  |
| 17.3 | Reconciliación de imports con `expected`     | ✅     | —  |

### Fase 18 — Charting library

| Fase | Nombre                                       | Estado | PR |
|------|----------------------------------------------|--------|----|
| 18.1 | Web — Recharts (balance + i/e + donut)       | ✅     | —  |
| 18.2 | Mobile — react-native-gifted-charts (polish) | ✅     | —  |

### Fase 19 — Bank mappings (auto-aprendizaje en imports)

| Fase | Nombre                                                 | Estado | PR |
|------|--------------------------------------------------------|--------|----|
| 19   | Bank-concept ↔ category mappings con auto-learn        | ✅     | —  |

### Fase 20 — Rules engine + seed bancos españoles + AI suggest

| Fase | Nombre                                                 | Estado | PR |
|------|--------------------------------------------------------|--------|----|
| 20   | Rules engine + seed (~30 reglas) + Ollama suggest      | ✅     | —  |

### Fase 21 — Cuentas, transferencias internas y patrimonio

| Fase | Nombre                                                 | Estado | PR |
|------|--------------------------------------------------------|--------|----|
| 21.1 | Categorías color/icon + presets cross-platform         | ✅     | —  |
| 21.2 | Accounts module + onboarding + account_id obligatorio  | ✅     | —  |
| 21.3 | Transfers + matcher + saldos + filtro cuenta + balances| ✅     | —  |

### Fase 22 — Módulo de deuda

| Fase | Nombre                                                 | Estado | PR |
|------|--------------------------------------------------------|--------|----|
| 22   | Liabilities + amortización francesa + KPIs salud deuda | ✅     | —  |

### Fase 23 — Transferencias internas: flag + convertir desde tx

| Fase | Nombre                                                       | Estado | PR |
|------|--------------------------------------------------------------|--------|----|
| 23   | Tercer kind transfer + UI sospechosas en /transfers          | ✅     | —  |
| 23.1 | `Category.is_transfer` flag + convertir tx a transferencia + cuenta destino | ✅     | —  |

### Fase 24 — Operaciones financiadas (deuda con plan de pago)

| Fase | Nombre                                                       | Estado | PR |
|------|--------------------------------------------------------------|--------|----|
| 24   | Convertir tx en operación financiada + crear liability al vuelo + badge en import preview | ✅     | —  |
| 24.1 | Cuotas persistidas editables + marcar pagada                 | ✅     | —  |
| 24.2 | TIN + TAE separados + tarjetas financiadas con plan fijo     | ✅     | —  |
| 24.3 | Total a pagar (banco) + cargos derivados dinámicamente       | ✅     | —  |

### Fase 25 — Drill-down de categoría desde el desglose

| Fase | Nombre                                                       | Estado | PR |
|------|--------------------------------------------------------------|--------|----|
| 25   | Página de detalle al pinchar una categoría + "Otros" expandible | ✅     | —  |

### Fase 26 — Imports hardening (XLSX smart + capital obligatorio + errores PDF)

| Fase | Nombre                                                       | Estado | PR |
|------|--------------------------------------------------------------|--------|----|
| 26   | Parser XLSX inteligente (auto-roles) + tolerancia a cabeceras desplazadas + capital obligatorio en loan/mortgage + mensajes PDF claros | ✅     | —  |

### Fase 27 — Selector temporal + filtros sincronizados con URL

| Fase | Nombre                                                       | Estado | PR |
|------|--------------------------------------------------------------|--------|----|
| 27   | TimeSelector reutilizable (años + meses sólo con datos) en transacciones y drill-down de categoría + filtros viajan en la URL | ✅     | —  |

### Fase 28 — Transferencias con cuenta ordenante / beneficiaria explícita

| Fase | Nombre                                                       | Estado | PR |
|------|--------------------------------------------------------------|--------|----|
| 28   | Modal con dos slots (ordenante/beneficiaria) + fuerza categoría canónica al kind correcto (fix de la dirección inferida desde category.kind) | ✅     | —  |

### Fase 29 — Refactor visual Análisis + chrome global (copper brand)

| Fase | Nombre                                                       | Estado | PR |
|------|--------------------------------------------------------------|--------|----|
| 29.1 | Copper brand tokens (azul → cobre alineado con el logo)      | ✅     | —  |
| 29.2 | Sidebar refactor (items grandes + ico-wraps + CTA gradient)  | ✅     | —  |
| 29.3 | Header chrome (bell+dot, currency pill, user chip, divisores) | ✅    | —  |
| 29.4 | Section tabs con iconos + count badges + underline copper    | ✅     | —  |
| 29.5 | PositionHero (fusión BalancesCard + DebtHealthCard) en /analysis | ✅ | —  |
| 29.6 | Polish cards (donut hover-center, sparkline, centered bar, tooltip Neto) | ✅ | — |

### Fase 30 — Rediseño módulo deuda en dos capas

Planificación + ADR + wireframe en
[`phases/README.md`](phases/README.md) (plan ejecutivo conjunto con
PHASE-31), [`decisions/0003-debt-module-two-layer-architecture.md`](decisions/0003-debt-module-two-layer-architecture.md)
y [`design-explorations/debt-redesign-30/wireframe.md`](design-explorations/debt-redesign-30/wireframe.md).

| Fase | Nombre                                                       | Estado | PR |
|------|--------------------------------------------------------------|--------|----|
| 30.1 | Enum `categories.role` + migración backfill desde `is_transfer` | ✅  | —  |
| 30.2 | Endpoint `/debt/category-summary` + bandas BdE 30/35% + fix `time_to_payoff` | ✅ | — |
| 30.3 | Web: rediseño `/debt` con Capa 1 hero                        | ✅     | —  |
| 30.4 | Web: Capa 2 condensada + vinculación contrato-categoría      | ✅     | —  |
| 30.5 | Mobile parity                                                | ✅     | —  |
| 30.6 | Selector de divisa del header propagado a los 3 endpoints de deuda | ✅ | — |
| 30.7 | Selector temporal `month/quarter/year` (alineado con `StitchPeriodToggle`) + donut por tipo de cuenta vinculada | ✅ | — |
| 30.8 | Navegador de período (Capa 1) con flechas acotadas a datos + KPIs period-scoped | ✅ | — |
| 30.9 | Serie diaria del saldo de deuda (`range=month`) + chart combo emisión/amortización | ✅ | — |

### Fase 31 — Saneamiento de cuentas e integridad de saldos

| Fase | Nombre                                                       | Estado | PR |
|------|--------------------------------------------------------------|--------|----|
| 31.1 | Seed bidireccional de transferencias + categoría INCOME + migración con backfill | ✅ | — |
| 31.2 | UI bulk-fix: detección y corrección de transferencias con dirección dudosa | ✅ | — |
| 31.3 | `else_=0` para tx sin categoría + banner UX                  | ✅     | —  |
| 31.4 | Brokerage/crypto fuera del patrimonio neto agregado          | ✅     | —  |
| 31.5 | `_infer_transfer_kind` robustecido (no asume EXPENSE arbitrario, respeta categoría preexistente) | ✅ | — |

> Pre-requisito completado antes de PHASE-30. Hotfix SQL aplicado al
> usuario `membrij7@gmail.com` (~7 tx, ~€11.7k recategorizadas) durante
> la implementación.

### Fase 32 — Cuenta principal, reasignación e integridad de transferencias

| Fase | Nombre                                                       | Estado | PR |
|------|--------------------------------------------------------------|--------|----|
| 32   | `accounts.is_default` (cuenta principal = ahorro neto, pre-seleccionada) + `POST /transactions/reassign-account` (consolidar mes) + fix dirección de transferencias en imports + invalidación debt al mutar cuentas | ✅ | — |

> Detalle en [`phases/phase-32-default-account-and-transfer-direction.md`](phases/phase-32-default-account-and-transfer-direction.md).
> Código completo y verde (FE + 445 tests BE); en `main` (commit `5a5fc74`,
> 2026-06-26).

### Fase 33 — Transferencias internas: overhaul de UX e integridad

| Fase | Nombre                                                       | Estado | PR |
|------|--------------------------------------------------------------|--------|----|
| 33   | Overhaul transversal (web + móvil) en 8 entregas: detección ES (BIZUM/TRASPASO) en sospechosas + badge de 3 estados (par/huérfana/deuda) + grupo "Transferencias" en el combobox + canal "A revisar" separado de "Errores" en imports + lenguaje cotidiano + dirección explícita en móvil + guard 409 al editar una pata emparejada | ✅ | — |

> Detalle en [`phases/phase-33-transfers-ux.md`](phases/phase-33-transfers-ux.md).
> Código completo y verde (FE: 67 web + 18 móvil · BE: 560 tests · ruff +
> mypy); en `main` (commits transfers-ux P1–P8, `8ae798e`…`5527f61`, 2026-06-26).

### Fase 34 — La verdad del dinero vive en la transacción (`flow`)

| Fase | Nombre                                                       | Estado | PR |
|------|--------------------------------------------------------------|--------|----|
| 34   | Columna `transactions.flow` (IN/OUT/TRANSFER_*) como fuente de verdad del dinero (ADR-0004): saldo + cashflow derivan de `flow`+`account.nature`, no de la categoría. Import y forms escriben `flow` (signo del extracto = invariante duro); `classify_import_flow` detecta transferencias y pago/liquidación de tarjeta; absorción del "cargo espejo" del `ADEUDO`; "Cuadrar saldo" + recategorización en bloque; saldo = caja real | ✅ | — |

> Detalle en [`phases/phase-34-transaction-flow.md`](phases/phase-34-transaction-flow.md)
> y [`decisions/0004-transaction-level-money-truth.md`](decisions/0004-transaction-level-money-truth.md).
> Código completo y verde (BE: 589 tests · ruff · mypy · FE: 71 web + 18
> móvil · typecheck · lint). Cierra la familia de lecciones PHASE-23.1/28/32.
> En `main` (squash `5215a80`, 2026-07-04, junto con PHASE-35 y PHASE-36).

### Fase 35 — Compras a plazos bajo una tarjeta (`parent_account_id`)

| Fase | Nombre                                                       | Estado | PR |
|------|--------------------------------------------------------------|--------|----|
| 35   | `accounts.parent_account_id`: una tarjeta agrupa varias compras financiadas a plazos, cada una con su cuadro propio. FE: alta de compra a plazos bajo una tarjeta + agrupación padre→hijas con total combinado en `/debt` + ocultar hijas de los selectores de transacción/import | ✅ | — |

> Detalle en [`phases/phase-35-installment-cards.md`](phases/phase-35-installment-cards.md).
> Convive con PHASE-34 en la misma rama. Backend + frontend completos y
> verdes. En `main` (squash `5215a80`, 2026-07-04, junto con PHASE-34 y PHASE-36).

### Fase 36 — Saldo de deuda gobernado por el cuadro + reconciliación

| Fase | Nombre                                                       | Estado | PR |
|------|--------------------------------------------------------------|--------|----|
| 36   | El saldo vivo de una liability con plan sale de las cuotas no pagadas del cuadro (`schedule_outstanding`); `POST /accounts/reconcile-debt` marca pagadas las cuotas desde los movimientos reales del extracto (amortización de préstamo FIFO + cargo agregado de tarjeta financiada), sin patas sintéticas ni tocar el cashflow. Ancla temporal para cuotas previas a los datos, exceso como `assumed_unregistered_debt`. Idempotente + reversible (`dry_run`) | ✅ | — |

> Detalle en [`phases/phase-36-schedule-driven-debt-reconciliation.md`](phases/phase-36-schedule-driven-debt-reconciliation.md).
> En `main` (squash `5215a80`, 2026-07-04, `Refs: PHASE-34, PHASE-35, PHASE-36`).
> Documentada retroactivamente (la fase se plegó en el squash sin doc propia).

### Fase 37 — Rediseño módulo Análisis + saneamiento de deuda

| Fase | Nombre                                                       | Estado | PR |
|------|--------------------------------------------------------------|--------|----|
| 37.1 | Serie temporal de patrimonio + `signed_amount_expr` + Δ-periodo | ✅ | — |
| 37.2 | KPI strip + grid ancho + cuentas colapsables + donut top-6   | ✅     | —  |
| 37.3 | Gasto estructural vs puntual + tasa de ahorro dual (`is_exceptional`) | ✅ | — |
| —    | Bugfix: autoaprendizaje no fija categoría para concepto de dirección ambigua (BIZUM) | ✅ | — |
| —    | Deuda: interés y deuda viva desde el cuadro de amortización (MUX por pasivo) | ✅ | — |
| 37.4 | Proyección fin de mes + runway (`/analytics/month-outlook`)  | ✅     | —  |
| 37.5 | Smart Insights v2 (no-redundancia + insights derivados)      | ✅     | —  |
| 37.6 | Mobile parity (month-outlook + insights v2 + filtro estructural donut + composición deuda + evolución patrimonio) | ✅ | — |

> Detalle en [`phases/phase-37-analysis-redesign.md`](phases/phase-37-analysis-redesign.md)
> (as-built) y [`phase-37-analysis-redesign.md`](phase-37-analysis-redesign.md) (plan).
> **En `main`** (push directo, fast-forward hasta `89eea70`, 2026-07-12; sin PR).
> 643 tests BE + 95 web + 18 móvil · mypy · ruff · lint · typecheck verdes.

### Fase 38 — Cuota de compra a plazos = gasto de caja + estandarización de layout web

Solo web + backend (sin paridad móvil). No hay migraciones ni endpoints nuevos.

| Fase | Nombre                                                       | Estado | PR |
|------|--------------------------------------------------------------|--------|----|
| 38.1 | Carve-out `is_card_financed_op` en `classify_import_flow`: la CUOTA de una compra a plazos con tarjeta cuenta como gasto real (`flow=OUT`); ADEUDO/liquidación y creación de deuda siguen neutros | ✅ | — |
| 38.2 | UX deuda-como-gasto: el form fija el segmento Gasto/Ingreso desde `category.kind` + badge "Pago de deuda" (`role=DEBT_PAYMENT/DEBT_INTEREST`) en la lista | ✅ | — |
| 38.3 | Estandarización layout web: tokens `layout.{pageWide,pageNarrow}` + `Card`/`CardTitle`/`CardHeader` (padding `lg` por defecto, `compact` opt-in) en ~22 páginas y 5 cards | ✅ | — |
| —    | Housekeeping: `type: ignore[attr-defined]` en `rowcount` (auth + transactions repos) · poda de backlog | ✅ | — |

> Detalle en [`phases/phase-38-installment-cash-expense-and-web-layout.md`](phases/phase-38-installment-cash-expense-and-web-layout.md).
> Cierra la familia de lecciones PHASE-34/37/38 sobre "qué es un pago de deuda".
> **En `main`** (commit `ac3b456`, push directo `89eea70`, 2026-07-12; sin PR).
> Sin paridad móvil todavía y sin prueba manual previa al merge (follow-ups).

### Fase 39 — Saldo del extracto como ancla del saldo real

| Fase | Nombre                                                       | Estado | PR |
|------|--------------------------------------------------------------|--------|----|
| 39   | Columna Saldo del extracto capturada por fila (`transactions.statement_balance`) + auto-anclaje del `opening_balance` al confirmar imports (misma semántica que "Cuadrar saldo", a fecha del extracto) + `accounts.anchored_statement_balance` para re-derivar al importar historia vieja + UI (mapping, preview, toast) | 🚧 | — |

> Detalle en [`phases/phase-39-statement-balance-anchor.md`](phases/phase-39-statement-balance-anchor.md).
> Código completo y verde (BE: 666 tests · ruff · mypy · FE: 95 web + types/services).
> Pendiente: prueba manual (reimportar extractos BBVA) + commit. Origen:
> auditoría de integridad [`audits/2026-07-13-data-integrity-pending-check.md`](audits/2026-07-13-data-integrity-pending-check.md).

### Fase 40 — Flag `counts_as_debt` (tarjeta revolving fuera de deuda)

| Fase | Nombre                                                       | Estado | PR |
|------|--------------------------------------------------------------|--------|----|
| 40   | `accounts.counts_as_debt` (default true): una tarjeta pagada íntegra cada mes se excluye del módulo de deuda (deuda viva, DTI, composición, historia, movimientos) pero se mantiene en el patrimonio neto. Backend (columna + migración + debt_health/history/service) + FE (tipo + toggle en el form) | ✅ | — |

> Sin doc de fase propia (documentada inline). En `main` (commit `5c1d01c`,
> junto con PHASE-41, 2026-07-15).

### Fase 41 — Simplificación del módulo Finanzas Domésticas

| Fase | Nombre                                                       | Estado | PR |
|------|--------------------------------------------------------------|--------|----|
| 41   | Retirada de la pestaña Transferencias + maquinaria de emparejado heurístico (ADR-0005 T4) · papelera atómica del par (borrar arrastra la pareja, restaurar re-vincula) · tickets heredan auto-categoría + `flow=OUT` · `MisclassifiedSection` movido a Transacciones. Conserva load-bearing (`link`/`unlink`, `from-source`/`-debt`). NO se fusionaron los motores de recurrencia (falso positivo del análisis) | ✅ | — |

> Detalle en [`phases/phase-41-module-simplification.md`](phases/phase-41-module-simplification.md).
> Origen: análisis de utilidad financiera de las pestañas. En `main` (commits
> `5c1d01c`…`9c9f47f`, push directo, 2026-07-15). BE 668 tests · mypy · ruff ·
> FE typecheck · lint · web 101 + móvil 18.

### Fase 42 — Rango de fechas personalizado (fuera trimestral)

| Fase | Nombre                                                       | Estado | PR |
|------|--------------------------------------------------------------|--------|----|
| 42   | Fuera `quarter`; dentro rango libre `custom` (from/to) end-to-end (Análisis + Dashboard + Deuda, web + móvil) · backend `date_from/date_to` en `by-month` y `debt/category-summary` (day-exact, bordes parciales) + nuevo `GET /accounts/position-as-of` · consistencia: Ingresos vs Gastos = totales del periodo, patrimonio a fecha de fin de rango, chart de patrimonio respeta el toggle "incluir deuda" | ✅ | — |

> Detalle en [`phases/phase-42-custom-date-range.md`](phases/phase-42-custom-date-range.md).
> En `main` (commits `209b31a` · `c22fc94` · `693fad0`, push directo,
> 2026-07-16). BE 673 tests · mypy · ruff · FE typecheck · lint · web 106 +
> móvil 18. Datos del periodo validados al céntimo contra `transactions`.
> Follow-up: paridad móvil de "Ingresos vs Gastos" (totales de periodo).

### Fase 43 — Split dashboard/análisis (ADR-0006) + saneamiento

| Fase | Nombre                                                       | Estado | PR |
|------|--------------------------------------------------------------|--------|----|
| 43   | Dashboard = balance/stocks (patrimonio + tarjetas de módulo: veredicto + número + link), Análisis = cuenta de resultados/flujos (ADR-0006) · `expense_nature` (estructural vs puntual) + recurrencia + smart insights v2 · patrimonio con pasivos dirigidos por el cuadro (un préstamo amortiza en el neto y cuadra con Deuda / `get_balances`) · tarjeta Deuda del dashboard period-scoped · `debt_movement_bounds` sólo cuenta cuotas pagadas (el navegador no cae en meses sin datos) · guardarraíles de calendario (re-clamp del ancla, rango acotado a días con datos, popover que voltea en el borde) · poda de código muerto (knip ~2.3k LoC + vulture) cableada a `make verify` | ✅ | — |

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

| Fase | Nombre                                                       | Estado | PR |
|------|--------------------------------------------------------------|--------|----|
| 44.1 | Cimientos: 8 enums nativos + 13 tablas (catálogo/fundamentales/umbrales/precios globales · cartera/análisis scoped) + migración reversible (`alembic check` verde) + ADR-0007 tablas globales + tests de modelo | 🚧 | — |
| 44.2 | Engine puro Capa 1: `CanonicalStatement` (48 partidas) + convenciones §4.5 (media t/t−1, guardas, hueco ≠ 0) + 17 derivaciones §4.4 + 27 métricas base con bandas + DuPont + banderas `ebt_divergence`/`fcf_divergence` | 🚧 | — |
| 44.3 | Engine capas 1.5 y 2: evolutiva (E1 horizontal · E2 common-size · E3 σ de márgenes · E4 crecimiento sostenible · cruces C1-C8) + forense (M-Score, Z'', F-Score, accruals, F5, F6, FZ, F7 con desglose) + catálogo agregado de 37 métricas | 🚧 | — |
| 44.4 | Engine Capa 3 (dividendo): cobertura D1-D8 · calidad de caja Q1-Q5 (Q4 anomalía fiscal) · soporte de balance B1-B4 (B4 dividendo financiado con deuda) · trayectoria T1-T4 · ajuste REIT sobre FFO · helpers `population_stdev`/`cagr` compartidos · catálogo agregado de 51 métricas | 🚧 | — |

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
