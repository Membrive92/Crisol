# Internal Docs — Finanzas App

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
