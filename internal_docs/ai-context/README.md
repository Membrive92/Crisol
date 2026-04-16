# AI Context

Contexto de consulta bajo demanda para Claude Code (y cualquier otro agente de
IA que trabaje en el proyecto).

Este directorio **no** contiene documentación oficial del proyecto — eso vive
en `internal_docs/` directamente. Aquí va información que ayuda a Claude a
tomar mejores decisiones cuando la necesita, pero que no tiene por qué
cargarse siempre en contexto.

---

## Qué va aquí

Ejemplos de lo que tiene sentido guardar:

- **Glosario del dominio financiero** — términos técnicos (conciliación,
  partida doble, cash flow, etc.) con la definición operativa que usamos
  nosotros.
- **Ejemplos reales anonimizados** — muestras de tickets, CSVs bancarios,
  formatos de exportación de apps populares, para iterar parsers y prompts.
- **Notas de evaluación de modelos** — qué modelo de visión probamos, con qué
  resultados, en qué casos falla. Útil para decidir cambios de modelo sin
  repetir pruebas.
- **Convenciones de negocio del usuario** — cómo clasificamos los gastos,
  qué categorías hay por defecto, qué monedas soportamos, preferencias de
  UX no obvias.
- **Snippets y plantillas de prompts** — versiones iteradas, con notas de
  por qué una funcionó mejor que otra.
- **Investigación técnica** — benchmarks, comparativas, decisiones de
  librerías que no llegan a ADR pero conviene recordar.

---

## Qué NO va aquí

- Documentación de la arquitectura del proyecto → `internal_docs/architecture.md`.
- Decisiones formales → `internal_docs/decisions/` (ADRs).
- Documentación de fases completadas → `internal_docs/phases/`.
- Lecciones de errores → `internal_docs/lessons.md`.
- Credenciales, tokens, datos reales de usuarios — **nunca**.

---

## Cómo lo usa Claude

Claude Code **no** carga este directorio automáticamente. Cuando necesite
contexto adicional para una tarea, puede buscar aquí con `Grep` / `Read`.
Ejemplos:

- Al escribir un prompt nuevo → revisa `prompts/` si existe.
- Al añadir una categoría por defecto → revisa `domain-glossary.md` si existe.
- Al debuggear una extracción fallida → revisa `model-evaluations.md` si existe.

Claude también puede **añadir archivos aquí** cuando aprenda algo útil
durante una sesión que no encaje en lessons.md ni en un ADR.

---

## Estructura sugerida (vacía por ahora)

```
ai-context/
├── README.md               # este archivo
├── domain-glossary.md      # (futuro) términos del dominio financiero
├── model-evaluations.md    # (futuro) resultados de pruebas de modelos
├── prompts/                # (futuro) snippets y versiones de prompts
└── samples/                # (futuro) ejemplos anonimizados de tickets, CSVs...
```

No hay nada obligatorio que crear hoy. Este directorio crecerá de forma
orgánica a medida que el proyecto avance y Claude necesite recordar cosas.
