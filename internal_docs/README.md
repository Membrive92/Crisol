# Internal Docs — Finanzas App

Documentación viva del proyecto: arquitectura, metodología, estado por fase,
lecciones aprendidas y contexto de consulta para IA.

A medida que el proyecto avance, esta carpeta crecerá con documentos por fase,
ADRs (Architecture Decision Records), catálogo de endpoints y schema de BD.

## Índice

- [architecture.md](architecture.md) — arquitectura del sistema
- [development-spec.md](development-spec.md) — metodología y fases
- [lessons.md](lessons.md) — errores y reglas aprendidas
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
| 1.2  | Auth frontend    | ⏳     | —  |

### Fase 2 — Transacciones

| Fase | Nombre                  | Estado | PR |
|------|-------------------------|--------|----|
| 2.1  | Transactions backend    | ⏳     | —  |
| 2.2  | Transactions frontend   | ⏳     | —  |

### Fase 3 — Dashboard

| Fase | Nombre              | Estado | PR |
|------|---------------------|--------|----|
| 3.1  | Dashboard backend   | ⏳     | —  |
| 3.2  | Dashboard frontend  | ⏳     | —  |

### Fase 4 — Importación

| Fase | Nombre             | Estado | PR |
|------|--------------------|--------|----|
| 4.1  | Imports backend    | ⏳     | —  |
| 4.2  | Imports frontend   | ⏳     | —  |

### Fase 5 — IA: tickets

| Fase | Nombre              | Estado | PR |
|------|---------------------|--------|----|
| 5.1  | Receipts backend    | ⏳     | —  |
| 5.2  | Receipts frontend   | ⏳     | —  |

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
├── phases/                 # (se crea en PHASE-0.1) docs por fase completada
├── decisions/              # (se crea cuando toque) ADRs
├── api/                    # (se crea en PHASE-1.1) catálogo de endpoints
└── data-model/             # (se crea en PHASE-1.1) estado del schema
```

---

## Cómo usar estos documentos

- **Al empezar una fase**: lee la fase anterior en `phases/` (cuando exista) y
  revisa `lessons.md`.
- **Al terminar una fase**: crea `phases/phase-X.Y-*.md`, actualiza las tablas
  de arriba, y añade lo que corresponda a `api/` y `data-model/`.
- **Al tomar una decisión no trivial**: crea un ADR en `decisions/`.
- **Al corregir un error evitable**: añade una lección a `lessons.md`.
