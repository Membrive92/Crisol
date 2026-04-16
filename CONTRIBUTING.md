# Contribuir a Finanzas App

Este proyecto sigue un workflow de desarrollo incremental por fases, con cada
fase entregada en su propio PR a `main`. Consulta
[internal_docs/development-spec.md](internal_docs/development-spec.md) para el
desglose completo.

---

## Workflow resumido

1. Identifica la fase a trabajar en [internal_docs/development-spec.md](internal_docs/development-spec.md).
2. Lee [CLAUDE.md](CLAUDE.md), [internal_docs/architecture.md](internal_docs/architecture.md)
   y [internal_docs/lessons.md](internal_docs/lessons.md).
3. Crea una rama: `feat/phase-X.Y-nombre-corto`.
4. Implementa siguiendo las reglas.
5. `make verify` debe pasar en local.
6. Documenta la fase en `internal_docs/phases/`.
7. Abre PR. CI verde obligatorio (el workflow de CI se configurará en PHASE-0.1).
8. Squash merge a `main`. Elimina la rama.

---

## Convenciones de commits

Conventional commits + referencia a fase:

```
tipo(scope): descripción corta — Refs: PHASE-X.Y
```

Tipos aceptados: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `build`, `ci`, `perf`, `style`.

Ejemplos:
```
feat(auth): login con JWT y refresh token — Refs: PHASE-1.1
fix(transactions): aislamiento por user_id en filtros — Refs: PHASE-2.1
docs(phase-0.0): estructura inicial de documentación — Refs: PHASE-0.0
```

---

## Reglas de código

Son **obligatorias** — no negociables. Consulta [CLAUDE.md](CLAUDE.md) para la
lista completa. Resumen:

### Frontend (TypeScript)
- Sin `any`, sin `as` (salvo boundaries de API), sin `@ts-ignore`.
- Imports ordenados: externos → `@app/*` → relativos → types.
- `packages/ui/` no hace data fetching.
- Estado servidor → TanStack Query. Estado cliente → Zustand.
- Estilos → NativeWind/Tailwind. Nada de `StyleSheet.create` en `packages/`.

### Backend (Python)
- Módulo: `router → service → repository → models → schemas`.
- Queries con bind params, nunca string interpolation.
- Sin imports entre módulos — dependency injection.
- `Decimal` para dinero, nunca `float`.
- Toda query de dominio filtra por `user_id`.
- Funciones async por defecto.

---

## Pull Requests

- Un PR = una fase.
- Título = conventional commit del cambio principal.
- Descripción: qué, por qué, cómo probarlo, checklist (plantilla de PR se
  añadirá en PHASE-0.1).
- CI verde antes de merge (workflow se añade en PHASE-0.1).
- Squash merge.

---

## Antes de abrir un PR

Checklist obligatorio:

- [ ] `make verify` verde (a partir de PHASE-0.2, cuando exista código)
- [ ] Documentación de fase creada en `internal_docs/phases/`
- [ ] `internal_docs/README.md` actualizado
- [ ] Lecciones nuevas añadidas a `internal_docs/lessons.md` (si aplica)
- [ ] Flujo principal probado manualmente

---

## Lecciones aprendidas

Cada vez que corrijas un error que podía evitarse, añade una entrada a
[internal_docs/lessons.md](internal_docs/lessons.md) en el mismo PR. Esto es
parte del Definition of Done de cada fase.
