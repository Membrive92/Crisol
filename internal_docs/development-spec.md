# Development Spec — Finanzas App

> Metodología de desarrollo incremental + desglose de fases.
> Cada fase es una rama, un PR y un merge a `main` con CI verde.

---

## 1. Principios de desarrollo

1. **Una fase, un PR**. Cada fase se entrega como un único PR a `main`.
2. **Fase entregable**. Al merge, `main` siempre queda en un estado utilizable
   y verificable (lint + typecheck + tests verdes).
3. **Documentación sincronizada**. Toda fase se documenta en
   `internal_docs/phases/phase-X.Y-nombre.md` **antes** del merge.
4. **No anticipar**. No se implementa funcionalidad de fases futuras.
5. **Lecciones acumuladas**. Si cometes un error prevenible, se añade a
   `internal_docs/lessons.md` en el mismo PR.

---

## 2. Workflow de una fase

### 2.1. Preparación (antes de escribir código)

1. Lee esta spec y localiza la fase a implementar.
2. Lee `internal_docs/architecture.md` si la fase toca arquitectura.
3. Lee `internal_docs/phases/` de la fase anterior (si existe).
4. Lee `internal_docs/lessons.md` para no repetir errores.
5. Confirma el alcance con el usuario (si trabajas con Claude Code, con una
   propuesta escrita antes de tocar código).
6. Crea la rama:
   ```bash
   git checkout main
   git pull
   git checkout -b feat/phase-X.Y-nombre-corto
   ```

### 2.2. Implementación

- Sigue las reglas de [CLAUDE.md](../CLAUDE.md) estrictamente.
- Sigue las skills relevantes (frontend-best-practices, local-ai-integration).
- Backend modular: `router → service → repository → models → schemas`.
- Commits pequeños y temáticos. Conventional commits obligatorio:
  ```
  tipo(scope): descripción corta — Refs: PHASE-X.Y
  ```
  Tipos: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `build`, `ci`.
- Si necesitas una dependencia nueva, documéntala en
  `internal_docs/decisions/NNNN-nombre.md` (ADR breve).
- Si te desvías de la arquitectura, ADR también.

### 2.3. Verificación local

Antes de empujar:

```bash
make verify   # lint + typecheck + tests (frontend + backend)
```

**No pushes sin `make verify` verde.** Si CI se va a quejar, mejor saberlo
antes del PR.

Además, prueba manualmente el flujo principal tocado por la fase.

### 2.4. Documentación de la fase

Crea `internal_docs/phases/phase-X.Y-nombre.md` siguiendo la plantilla de la
sección 4 de este documento.

Actualiza:
- `internal_docs/README.md` — marca la fase como ✅ en la tabla.
- `internal_docs/api/endpoints.md` — si hay endpoints nuevos (archivo se crea en PHASE-1.1).
- `internal_docs/data-model/schema.md` — si hay migraciones (archivo se crea en PHASE-1.1).
- `internal_docs/lessons.md` — si aprendiste algo que podía evitarse.

### 2.5. Pull Request

```bash
git push -u origin feat/phase-X.Y-nombre-corto
gh pr create   # usa la plantilla de .github/pull_request_template.md
```

- Título del PR = mensaje del commit principal (conventional commits).
- Descripción sigue la plantilla: qué, por qué, cómo probarlo, checklist.
- Espera a que CI esté verde. **No hacer merge con CI en rojo.**
- **Squash merge** recomendado: mantiene `main` con un commit por fase.
- Tras el merge, elimina la rama.

### 2.6. Tras el merge

```bash
git checkout main
git pull
```

Si es el cierre de una fase mayor (1.x, 2.x…), crea un tag:

```bash
git tag -a v0.1.0 -m "Phase 1 complete — auth"
git push origin v0.1.0
```

Opcional: GitHub Release con notas.

---

## 3. Reglas de commits y PRs

### Commits

- Formato: `tipo(scope): descripción — Refs: PHASE-X.Y`
- Ejemplos:
  - `feat(auth): login con JWT y refresh token — Refs: PHASE-1.1`
  - `fix(transactions): aislamiento por user_id en filtros — Refs: PHASE-2.1`
  - `docs(phase-2.1): añadir documento de fase — Refs: PHASE-2.1`
- Idioma: español para descripciones, inglés para nombres técnicos.
- No mezclar fases en un mismo commit.

### PRs

- Un PR = una fase. No mezclar.
- Título = conventional commit del cambio principal.
- CI verde obligatorio.
- Revisión personal antes de merge: relee el diff completo.
- Squash merge.

---

## 4. Plantilla de documentación de fase

Copia este bloque a `internal_docs/phases/phase-X.Y-nombre.md`:

```markdown
# PHASE-X.Y — <nombre>

**Estado**: ✅ completada | 🚧 en curso | ⏳ pendiente
**Rama**: `feat/phase-X.Y-nombre`
**PR**: #<número>
**Fecha de merge**: YYYY-MM-DD

## Objetivo
<1-2 frases>

## Qué se implementó
- <bullet>
- <bullet>

## Flujo técnico
<descripción paso a paso o diagrama ASCII>

## Archivos clave
- `ruta/archivo.py` — <qué hace>
- `ruta/archivo.tsx` — <qué hace>

## Endpoints añadidos
- `POST /auth/login` — descripción

## Migraciones
- `NNNN_create_users.py`

## Verificación
- [ ] `make verify` verde
- [ ] Prueba manual: <pasos concretos>
- [ ] Tests de aislamiento multi-usuario (si aplica)

## Decisiones tomadas
- <bullet> (link a ADR si hay)

## Limitaciones conocidas
- <bullet>

## Próxima fase
PHASE-X.Z — <nombre>
```

---

## 5. Fases

### Fase 0 — Bootstrap

| Fase | Nombre | Entregable |
|------|--------|------------|
| **0.0** | Setup inicial (docs) | .gitignore, README, LICENSE, CONTRIBUTING, .env.example, CLAUDE.md, internal_docs/ (architecture, development-spec, lessons, ai-context). Primer push a `main`. |
| **0.1** | Bootstrap monorepo | pnpm workspaces, Turborepo, `apps/web` y `apps/mobile` arrancan vacíos, tooling compartido (eslint/prettier/tsconfig). `pnpm dev` funciona. |
| **0.2** | Bootstrap backend | FastAPI con endpoint `/health`. Postgres+pgvector en docker-compose. Alembic configurado. Primera migración vacía. `pytest` arranca. |
| **0.3** | Bootstrap Ollama | Servicio `ollama` en docker-compose. Modelo visión descargado. Módulo `backend/app/modules/ai/` con cliente + endpoint `/ai/health` que pinguea Ollama. |

### Fase 1 — Autenticación

| Fase | Nombre | Entregable |
|------|--------|------------|
| **1.1** | Auth backend | Módulos `users/` + `auth/`. Endpoints register, login, refresh, logout, me. JWT access + refresh con rotación. Argon2id. Tests de aislamiento. |
| **1.2** | Auth frontend | Pantallas login/register en web y mobile. Store de sesión (Zustand). Interceptor HTTP con refresh automático. Logout limpia estado. |

### Fase 2 — Transacciones y categorías

| Fase | Nombre | Entregable |
|------|--------|------------|
| **2.1** | Transactions backend | Módulos `categories/` + `transactions/`. CRUD completo. Filtros por fecha, categoría, texto. Aislamiento por user_id con tests. |
| **2.2** | Transactions frontend | Listado, formulario crear/editar, filtros. Web + mobile. Query keys centralizados. |

### Fase 3 — Dashboard

| Fase | Nombre | Entregable |
|------|--------|------------|
| **3.1** | Dashboard backend | Endpoints de agregación: balance, por categoría, por mes, top gastos. Todos filtrando por user_id. |
| **3.2** | Dashboard frontend | KPIs, gráfica de evolución, donut por categoría. Web + mobile. |

### Fase 4 — Importación de ficheros

| Fase | Nombre | Entregable |
|------|--------|------------|
| **4.1** | Imports backend | Módulo `imports/`. Parser CSV/Excel, mapeo de columnas configurable, deduplicación por hash. Estado del job persistido. |
| **4.2** | Imports frontend | Wizard de subida, preview de mapeo, resumen de resultados. Web (mobile opcional). |

### Fase 5 — IA: extracción de tickets

| Fase | Nombre | Entregable |
|------|--------|------------|
| **5.1** | Receipts backend | Módulo `receipts/`. Upload a MinIO. `ai.service.extract_receipt`. Prompt estructurado. Validación Pydantic. Endpoint `POST /receipts/extract`. Estado del receipt auditable. |
| **5.2** | Receipts frontend | Captura cámara (mobile) + upload (web). Pantalla de confirmación editable. Persistencia tras confirmación. |

---

## 6. Definition of Done de cada fase

Una fase no está completa hasta que **todo** lo siguiente es cierto:

- [ ] Código en rama `feat/phase-X.Y-...` mergeado a `main` vía PR.
- [ ] CI verde en el PR (desde PHASE-0.1 en adelante).
- [ ] `make verify` verde en local (desde PHASE-0.2 en adelante).
- [ ] Documento `internal_docs/phases/phase-X.Y-*.md` creado.
- [ ] `internal_docs/README.md` actualizado (fase marcada ✅).
- [ ] `internal_docs/api/endpoints.md` actualizado si hay endpoints (desde PHASE-1.1).
- [ ] `internal_docs/data-model/schema.md` actualizado si hay migraciones (desde PHASE-1.1).
- [ ] `internal_docs/lessons.md` actualizado si hubo errores evitables.
- [ ] Flujo principal probado manualmente.
- [ ] ADRs creadas en `internal_docs/decisions/` si hubo decisiones no obvias.

Si falta cualquiera de estas, la fase **no** se da por cerrada.
