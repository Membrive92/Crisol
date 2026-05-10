# PHASE-20 — Rules engine + seed inicial para bancos españoles + AI suggest

**Estado**: ✅ completada
**Rama**: directo a `main`
**Commit**: `8981ccd`
**Fecha de merge**: 2026-05-10

## Objetivo

Las equivalencias exactas (PHASE-19) sólo cubren el banco que el
usuario use; cambiar de banco rompe el aprendizaje. Esta fase añade
un motor de reglas con patrones (`contains`/`starts_with`/`exact`/`regex`)
sobre el concepto del banco y/o la descripción para clasificar
transacciones sin depender de equivalencias exactas. Se acompaña de
un seed inicial con ~30 reglas pre-pobladas para BBVA, Santander,
Sabadell, ING, Caixabank, Unicaja y Cajamar, y un fallback a IA
local (Ollama) para conceptos sin sugerencia.

## Qué se implementó

### Backend — módulo `category_rules`

`backend/app/modules/personal_finance/category_rules/`:

- **`models.py`** — tabla `category_rules` con
  `(user_id, pattern, match_type, field, category_id, priority,
  enabled)`. `match_type` enum: `EXACT | CONTAINS | STARTS_WITH |
  REGEX`. `field` enum: `CONCEPT | DESCRIPTION | BOTH`. Unique
  constraint `(user_id, pattern, match_type, field, category_id)`.
- **`repository.py`** — `find_first_matching_rule(rules, concept,
  description)` evalúa por `priority` ascendente y devuelve la
  primera que matchea. `list_rules_for_user(user_id, enabled_only)`.
- **`service.py`** + **`router.py`** — CRUD bajo `/category-rules`.

### Backend — módulo `seed`

`backend/app/modules/personal_finance/seed/`:

- **`dataset.py`** — ~18 categorías base + ~30 reglas pre-pobladas.
  Patrones cubren conceptos típicos del extracto + comercios habituales
  españoles. `priority` por convención: 10-29 muy específicas
  (Amazon Prime > Amazon, Abono Nómina), 30-49 sobre concepto,
  50-79 sobre description, 80+ genéricas (PAYPAL, TRANSFERENCIAS
  sin contexto).
- **`service.py`** — `seed_recommended(user_id)` idempotente: UPSERT
  por nombre case-insensible para categorías, UPSERT por
  `(pattern, match_type, field, category_id)` para reglas. Si la
  categoría existe pero falta `color`/`icon`, los rellena.
- **`router.py`** — endpoint `POST /seed/recommended` para usuarios
  existentes que quieran reseed (idempotente).
- Hook en `POST /auth/register` ejecuta `seed_recommended` para
  todo usuario nuevo.

### Cascada de categorización en imports

`backend/app/modules/personal_finance/imports/service.py` resuelve
la categoría de cada fila en este orden:

1. **Override del usuario en preview** (`category_overrides`).
2. **Equivalencia exacta** (`bank_category_mappings`, PHASE-19).
3. **Match exacto** por nombre de categoría existente.
4. **Reglas del usuario** (`category_rules`) por prioridad ascendente.
5. **`default_category_id`** del wizard (o `None`).

### AI suggest (Ollama)

`POST /imports/{job_id}/ai-suggest` — para los conceptos del preview
que **no** tienen sugerencia (ni mapping guardado ni regla matching),
consulta el modelo de texto local (Ollama) con el listado de
categorías del usuario y devuelve `{concept_normalizado: category_id | null}`.
El frontend muestra estas sugerencias con badge "IA"; al confirmar
el commit, las aceptadas se persisten como `bank_category_mappings`
nuevas.

### UI — página de reglas

`apps/web/app/(app)/settings/categories/rules/page.tsx` — CRUD de
reglas con previsualización de impacto sobre los últimos imports.

### Componentes UI compartidos

- `apps/web/components/ui/confirm-dialog.tsx` (nuevo) — dialog
  reusable para confirmaciones destructivas.
- `apps/web/components/ui/spinner.tsx` (nuevo).

## Flujo técnico

```
 Usuario nuevo se registra
    ▼
 POST /auth/register → seed_recommended(user_id)
    │ crea ~18 categorías + ~30 reglas pre-pobladas
    ▼
 Usuario sube extracto del banco
    ▼
 POST /imports/preview
    │ Para cada concepto único:
    │   1. saved_mapping?  → suggested
    │   2. rule(s) que matcheen TODAS las filas a la misma cat? → suggested
    │   3. None
    ▼
 Frontend muestra sugerencias con badge según source
    │ Para conceptos sin sugerencia, botón "Pedir IA"
    ▼
 POST /imports/{job_id}/ai-suggest
    │ ai.service.suggest_categories_for_concepts(pending, cats)
    │ → modelo local (Ollama) responde {concept: category_id | null}
    ▼
 Usuario confirma o corrige
    ▼
 POST /imports/{job_id}/commit { category_overrides }
    │ overrides aceptados → bank_category_mappings + tx con su category_id
```

## Archivos clave

- `backend/app/modules/personal_finance/category_rules/` (módulo nuevo)
- `backend/app/modules/personal_finance/seed/` (módulo nuevo)
- `backend/alembic/versions/i6d83e4f29a5_category_rules.py`
- `backend/alembic/versions/g4b89c612e07_normalize_enum_casing.py`
  (bugfix transversal: alinea enums TransactionSource/FixedExpenseStatus
  al casing UPPER que SQLAlchemy genera desde StrEnum)
- `backend/alembic/versions/f3a78b5c19d0_imports_preview_state.py`
  (estado de preview en `import_jobs.preview_payload`)
- `backend/tests/test_category_rules.py`
- `backend/tests/test_seed.py`
- `apps/web/app/(app)/settings/categories/rules/page.tsx`
- `apps/web/components/imports/preview-step.tsx` (componente nuevo
  del wizard que muestra grupos por concepto)

## Endpoints añadidos

- `GET /category-rules` — lista reglas del usuario.
- `POST /category-rules` — crea regla.
- `PUT /category-rules/{id}` — actualiza.
- `DELETE /category-rules/{id}` — elimina.
- `POST /seed/recommended` — reseed idempotente.
- `POST /imports/{job_id}/ai-suggest` — sugerencias por IA local.

## Migraciones

- `f3a78b5c19d0_imports_preview_state.py` — `import_jobs.preview_payload`
  JSONB nullable.
- `g4b89c612e07_normalize_enum_casing.py` — alinea `transactionsource`
  y `fixedexpensestatus` enums a UPPER (SA emite el `name` del
  StrEnum, no el `value`).
- `i6d83e4f29a5_category_rules.py` — tabla `category_rules` +
  enums `rulematchtype` y `rulefield` + index + unique constraint.

## Verificación

- [x] `pytest backend/tests/test_category_rules.py` verde.
- [x] `pytest backend/tests/test_seed.py` verde.
- [x] `seed_recommended` ejecutado dos veces consecutivas: la segunda
      no duplica nada (idempotencia).
- [x] AI suggest: pedir sugerencia para 3 conceptos desconocidos
      (Ollama corriendo local con modelo de texto) → respuesta
      mapeada a category_ids del usuario.
- [x] Preview de imports muestra grupos por concepto con
      sugerencia + source (`saved_mapping` | `rule` | `ai`).

## Decisiones tomadas

- **Reglas por usuario, no globales**. Cada usuario puede tener
  sus reglas propias. El seed crea las recomendadas en su namespace
  — si las borra o edita, sólo le afecta a él.
- **Prioridad ascendente** (`priority=10` gana a `priority=100`).
  Más intuitivo que el orden inverso. Las reglas del seed van en
  rangos 10-79; las custom del usuario por defecto en `priority=100`
  para no chocar.
- **Match `BOTH` por defecto** — el patrón se evalúa contra concepto
  Y descripción. Cubre el caso común "mi regex matchea 'PAYPAL' en
  cualquiera de los dos campos".
- **AI suggest es opt-in**. No se llama automáticamente al cargar
  el preview; el usuario tiene que pulsar "Pedir IA" porque la
  inferencia local con qwen2.5 en CPU tarda 30-90s. Latencia
  visible que requiere consentimiento explícito.
- **El seed completa campos vacíos sin sobrescribir**. Si el usuario
  ya tiene "Restaurantes" creada con su color/icon propios, el
  reseed no los toca; sólo rellena los `NULL`.
- **Migración de enum casing como bugfix transversal**. Se descubrió
  al añadir `transactionsource = 'expected'` en PHASE-17.2 — el
  enum había quedado con valores lowercase mientras SQLAlchemy
  emitía UPPER. La migración añade los UPPER y migra datos
  existentes; los lowercase quedan como huérfanos inofensivos
  (Postgres no permite `DROP VALUE` sin recrear el tipo).

## Limitaciones conocidas

- **Reglas no editables en mobile** — la pantalla `/settings/categories/rules`
  es web-only por ahora. Mobile lista las categorías pero no las reglas.
- **AI suggest depende de Ollama corriendo local**. Si el daemon
  no está, devuelve 502 y el frontend muestra error. No hay
  fallback a OpenAI ni servicio remoto (privacidad por diseño).
- **No hay test de extremo-a-extremo del flujo seed → preview con
  sugerencias**. Los tests cubren cada pieza por separado pero
  no la integración completa con datos realistas.
- **El normalize_concept de bank_mappings es básico** (casefold +
  trim). Conceptos con caracteres unicode raros (ñ vs n) crean
  rows distintos.

## Próxima fase

PHASE-21.1 — Personalización de categorías con color y emoji.
