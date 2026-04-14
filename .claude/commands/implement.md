# Implementar una fase del proyecto

Vas a implementar la fase: $ARGUMENTS

## Workflow obligatorio

### 1. Preparación
- Lee internal_docs/development-spec.md y busca la fase indicada
- Lee la documentación de la fase anterior en internal_docs/phases/
- Lee internal_docs/architecture.md si la fase toca arquitectura
- Lee internal_docs/lessons.md para no repetir errores conocidos
- Lee la skill relevante (frontend-best-practices, local-ai-integration)
- Confirma conmigo el alcance antes de escribir código

### 2. Rama
- `git checkout main && git pull`
- `git checkout -b feat/phase-X.Y-nombre-corto`

### 3. Implementación
- Sigue el patrón del stack (router → service → repository para backend)
- Sigue las reglas de CLAUDE.md estrictamente
- Si necesitas instalar una dependencia no prevista, pregunta primero
- Si necesitas desviarte de la arquitectura, documenta en internal_docs/decisions/
- Commits pequeños: `tipo(scope): descripción — Refs: PHASE-X.Y`

### 4. Verificación local
- `make verify` verde (lint + typecheck + tests, frontend y backend)
- Prueba manualmente el flujo principal
- NO pushear con make verify en rojo

### 5. Documentación
- Crea internal_docs/phases/phase-X.Y-nombre.md siguiendo la plantilla de internal_docs/development-spec.md
- Actualiza internal_docs/README.md (tabla de estado → ✅)
- Actualiza internal_docs/api/endpoints.md si añadiste endpoints
- Actualiza internal_docs/data-model/schema.md si modificaste el modelo
- Actualiza internal_docs/lessons.md si hubo errores evitables

### 6. Pull Request
- `git push -u origin feat/phase-X.Y-nombre-corto`
- `gh pr create` usando la plantilla de .github/pull_request_template.md
- Espera a que CI esté verde (frontend + backend jobs)
- Confirma conmigo antes del merge
- Squash merge a main
- `git checkout main && git pull && git branch -d feat/phase-X.Y-nombre-corto`

NO avances a la siguiente fase sin mi confirmación tras el merge.
