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
| 30.4 | Web: Capa 2 condensada + vinculación contrato-categoría      | 📋     | —  |
| 30.5 | Mobile parity (opcional, aplazable)                          | 📋     | —  |

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
