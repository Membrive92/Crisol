<!--
Título del PR: sigue conventional commits
  feat(scope): descripción — Refs: PHASE-X.Y
-->

## Fase
`PHASE-X.Y — <nombre>`

## Objetivo
<1-2 frases explicando qué aporta este PR.>

## Cambios
- <bullet>
- <bullet>

## Endpoints añadidos o modificados
- `METHOD /ruta` — descripción

## Migraciones
- `NNNN_descripcion.py`

## Cómo probarlo
1. <paso>
2. <paso>

## Checklist obligatorio

- [ ] `pnpm lint && pnpm typecheck && pnpm test` verde en local
- [ ] Documentación de fase creada en `internal_docs/phases/phase-X.Y-*.md`
- [ ] `internal_docs/README.md` actualizado (fase marcada ✅)
- [ ] `internal_docs/lessons.md` actualizado (si hubo errores evitables)
- [ ] Flujo principal probado manualmente
- [ ] No hay `any`, `as` innecesario, `@ts-ignore`, ni `float` para dinero
- [ ] Toda query de dominio filtra por `user_id` (cuando haya backend)

## Capturas / demo
<si aplica>

## Notas para el reviewer
<opcional>
