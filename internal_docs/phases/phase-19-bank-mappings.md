# PHASE-19 — Bank-concept ↔ category mappings (auto-aprendizaje)

**Estado**: ✅ completada
**Rama**: directo a `main`
**Commit**: `c9172b8`
**Fecha de merge**: 2026-05-10

## Objetivo

Convertir las decisiones del usuario en el preview del wizard de
imports en aprendizaje persistente. Cuando el usuario asigna una
categoría a un concepto del banco ("PAGO TARJETA — RESTAURANTES"
→ Restaurantes), el sistema guarda esa equivalencia y la aplica
automáticamente en futuras importaciones del mismo concepto.

## Qué se implementó

### Backend — módulo `bank_mappings`

`backend/app/modules/personal_finance/bank_mappings/`:

- **`models.py`** — tabla `bank_category_mappings` con
  `(user_id, bank_concept_normalized, category_id)` + unique constraint
  por `(user_id, bank_concept_normalized)`.
- **`repository.py`** — `upsert_mapping(user_id, bank_concept, category_id)`,
  `get_mappings_for_concepts(user_id, concepts)` (lookup batch para no
  hacer N queries por preview), `normalize_concept(raw)` (casefold +
  trim + remove dobles espacios — la "huella" del concepto).
- **`service.py`** — wrapping con HTTPException para CRUD opcional.
- **`schemas.py`** + **`router.py`** — endpoints CRUD bajo `/bank-mappings`
  por si el usuario quiere gestionar a mano.

### Wiring en imports

El service de imports persiste los `category_overrides` del commit
como `bank_category_mappings` antes de procesar las filas. En la
siguiente importación, el preview consulta esas equivalencias y
las muestra como sugerencia (`suggestion_source='saved_mapping'`).

## Flujo técnico

```
 Usuario sube extracto del banco
    ▼
 POST /imports/preview → ImportJob(status=PREVIEW)
    │ + preview_payload: {rows, effective_mappings, ...}
    │ + bank_concept_groups: [{concept, count, suggested_category_id, ...}]
    ▼
 Frontend muestra grupos por concepto + dropdown de categoría
    │ usuario selecciona categorías para conceptos sin sugerencia
    ▼
 POST /imports/{id}/commit { category_overrides: {concept: category_id} }
    │ persist_user_category_overrides() → upsert en bank_category_mappings
    │ _process_and_persist() aplica las equivalencias guardadas
    ▼
 Próxima importación: preview ya viene con suggested_category_id
```

## Archivos clave

- `backend/app/modules/personal_finance/bank_mappings/` (módulo nuevo)
- `backend/alembic/versions/h5c92d703f18_bank_category_mappings.py`
- `backend/tests/test_bank_mappings.py`
- `packages/services/src/api/endpoints/bank-mappings.ts`
- `packages/services/src/query/hooks/useBankMappings.ts`

## Endpoints añadidos

- `GET /bank-mappings` — lista equivalencias del usuario.
- `POST /bank-mappings` — upsert manual.
- `DELETE /bank-mappings/{id}` — borra una equivalencia.

## Migraciones

- `h5c92d703f18_bank_category_mappings.py` — tabla `bank_category_mappings`
  + index `ix_bank_category_mappings_user_id` + unique
  `uq_bank_category_mappings_user_concept`.

## Verificación

- [x] `pytest backend/tests/test_bank_mappings.py` verde.
- [x] `pnpm typecheck` y `pnpm lint` verdes.
- [x] Preview de imports muestra `suggested_category_id` para
      conceptos con mapping previo.
- [x] Tras commit, el mapping aparece en `GET /bank-mappings`.

## Decisiones tomadas

- **`normalize_concept` antes de comparar**. El banco devuelve el
  mismo concepto con espacios y casing variables — almacenamos la
  forma normalizada y comparamos contra esa. Evita duplicados como
  `RESTAURANTE` vs `Restaurante` siendo dos rows distintos.
- **Upsert silencioso**. Si el usuario reasigna un concepto a otra
  categoría en un import posterior, el mapping se actualiza sin
  conflicto — no es un "histórico de decisiones" sino un "estado
  actual de mi preferencia".
- **No bloquear el commit por mapping inválido**. Si un
  `category_id` del override no pertenece al usuario (manipulación o
  bug del cliente), se ignora silenciosamente esa entry pero el
  resto del commit procede.

## Limitaciones conocidas

- Sin UI dedicada para gestionar mappings — el usuario edita a
  través del flujo de imports. Endpoint REST disponible si en una
  fase futura se quiere añadir pantalla de gestión.
- Match exacto (no fuzzy). Conceptos con typos del banco crean
  mappings nuevos; estos se solapan con los anteriores.

## Próxima fase

PHASE-20 — Rules engine + seed inicial para bancos españoles.
