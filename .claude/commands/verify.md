# Verificar fase completada

Verifica que la fase $ARGUMENTS está lista para PR y merge.

## Checks automáticos (local)
1. `make verify` verde (lint + typecheck + tests, frontend + backend)
2. Si falla algo, reporta exactamente qué y dónde

## Checks de documentación
3. ¿Existe internal_docs/phases/phase-X.Y-*.md?
4. ¿Sigue la plantilla de internal_docs/development-spec.md? (objetivo, qué se implementó, flujo técnico, archivos, verificación, limitaciones)
5. ¿Se actualizó internal_docs/README.md con el estado ✅?
6. ¿Se actualizó internal_docs/api/endpoints.md si se añadieron endpoints?
7. ¿Se actualizó internal_docs/data-model/schema.md si hubo migraciones?
8. ¿Se actualizó internal_docs/lessons.md si hubo errores evitables?
9. ¿Hay ADR en internal_docs/decisions/ si se tomaron decisiones no obvias?

## Checks de calidad
10. ¿Hay `any`, `@ts-ignore`, o `as` innecesario en el código nuevo?
11. ¿Alguna query de dominio sin filtro `user_id`?
12. ¿Alguna importación de librería de IA fuera de backend/app/modules/ai/?
13. ¿Algún `float` para importes monetarios?
14. ¿Las funciones públicas tienen JSDoc/docstring?
15. ¿Los tests cubren la lógica de negocio y el aislamiento multi-usuario?

## Checks de git / PR
16. ¿Estoy en una rama `feat/phase-X.Y-*` (no en main)?
17. ¿Los commits siguen conventional commits + `— Refs: PHASE-X.Y`?
18. ¿Hay PR abierto? Si sí, ¿CI verde?

Reporta cada check como ✅ o ❌ con detalle si falla. Si todo está ✅, confirma
que la fase está lista para merge.
