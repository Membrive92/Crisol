# PHASE-44.1 — Cimientos del módulo Inversión

**Estado**: ✅ código completo y verde (pendiente prueba manual del usuario)
**Rama**: trabajo directo sobre `main` (workflow del proyecto)
**Fecha**: 2026-07-19

## Objetivo

Poner los cimientos del módulo green-field **Inversión** (ARCH fase 40.1):
enums nativos, modelos SQLAlchemy, migración reversible y ADR de tablas
globales. Sin routers, sin servicios, sin frontend — solo el esqueleto de
datos sobre el que construyen las fases siguientes (engine, ingesta, cartera).

Fuente de verdad del diseño:
[`improvements/DESIGN-v2-investment-module.md`](../improvements/DESIGN-v2-investment-module.md)
(qué/porqué) y
[`improvements/ARCHITECTURE-investment-module.md`](../improvements/ARCHITECTURE-investment-module.md)
(cómo, §2.2 el DDL).

## Qué se implementó

- **8 enums nativos Postgres** (`app/modules/investment/enums.py`): `sector_internal`,
  `accounting_std`, `security_type`, `period_type`, `statement_source`,
  `job_status`, `threshold_direction`, `corp_action_type`. Helper `pg_enum()`
  persiste el `.value` del `StrEnum` (no el nombre del miembro) vía
  `values_callable`.
- **13 tablas** repartidas en 6 sub-paquetes:
  - `catalog/` — `securities` (global).
  - `fundamentals/` — `financial_statements` (48 partidas canónicas, todas
    NULLABLE), `restatement_flags`, `ingestion_jobs` (globales; job atribuido a
    usuario por auditoría).
  - `thresholds/` — `scoring_thresholds` (global).
  - `pricing/` — `price_quotes` (global, una fila viva por security).
  - `analysis/` — `analysis_runs` (scoped; scores de primer nivel en columnas +
    desgloses JSONB).
  - `portfolio/` — `inv_lots`, `inv_sales`, `inv_sale_allocations`,
    `inv_dividends_received`, `inv_corporate_actions`, `inv_lot_adjustments`
    (scoped).
- **ADR-0007** — excepción explícita al patrón multi-tenant: cuatro tablas de
  datos de mercado/regulatorios son GLOBALES (sin `user_id`).
- **Migración** `aa1b47c9d2e6f0_investment_module_foundations` — puramente
  aditiva, reversible, con parity `alembic check` verde.
- **Tests de modelo** (`tests/test_investment_models.py`, 11 tests): globales vs
  scoped, 48 partidas canónicas presentes y nullables, round-trip de enums
  nativos, defaults de servidor, `CheckConstraint` cantidad>0, `UniqueConstraint`.

## Archivos clave

- `backend/app/modules/investment/enums.py` — enums + `pg_enum()`.
- `backend/app/modules/investment/{catalog,fundamentals,thresholds,pricing,analysis,portfolio}/models.py`.
- `backend/alembic/versions/aa1b47c9d2e6f0_investment_module_foundations.py`.
- `backend/alembic/env.py` + `backend/tests/conftest.py` — imports de los modelos
  (para `Base.metadata` completo: `alembic check` en CI y `create_all` en tests).
- `internal_docs/decisions/0007-investment-global-tables.md`.

## Migraciones

- `aa1b47c9d2e6f0` (revises `f9v25x7us9w8v4`). 8 enums + 13 tablas. `downgrade`
  elimina las 13 tablas (orden inverso de FKs) y los 8 enums.

## Verificación

- [x] `ruff check` + `black --check` + `mypy app/` (152 ficheros) verdes.
- [x] `alembic heads` → un único head (`aa1b47c9d2e6f0`).
- [x] `alembic upgrade head` sobre BD limpia (cadena completa) OK.
- [x] `alembic check` → **"No new upgrade operations detected"** (parity
      modelo↔migración, el gate de CI).
- [x] `alembic downgrade -1` elimina las 13 tablas + 8 enums; `upgrade head`
      las restaura (reversibilidad).
- [x] `pytest tests/test_investment_models.py` → 11 passed.
- [x] Subconjunto DB-heavy (health, accounts, transactions, categories, debt,
      seed) → 105 passed (la migración/imports no rompen el schema compartido).
- [x] **Suite BE completa → 693 passed** (2026-07-20, 10m40s), excluyendo
      `test_ai_health.py` / `test_ai_service.py` (requieren Ollama arrancado).
      Confirma que la migración y los imports nuevos no rompen nada del resto
      del backend.
- [ ] Prueba manual del usuario (esta fase no tiene UI ni endpoints; la prueba
      real llega con el engine y la ingesta).

## Decisiones tomadas

- **Tablas globales** (securities, financial_statements, restatement_flags,
  scoring_thresholds, price_quotes) → [ADR-0007](../decisions/0007-investment-global-tables.md).
- **Índice `ix_runs_sec_user` plano** (sin `run_date DESC`): un btree plano sirve
  el `ORDER BY run_date DESC` vía scan hacia atrás y evita el índice de
  expresión que `alembic check` compara mal (falso positivo en CI).
- **Revisión del padre de la migración**: el head real era `f9v25x7us9w8v4`
  (PHASE-43.2), no `z3p58r0on2q1p7` — los revision IDs no son secuenciales;
  guiarse por el filename ordenado alfabéticamente induce a error.

## Limitaciones conocidas / follow-ups

- **Seed de `scoring_thresholds` diferido**: el criterio de salida de la ARCH
  fase 40.1 menciona "seed thresholds", pero las `metric_key` las fija el engine
  (fase 40.2/40.3) desde el catálogo §5. Sembrar ahora, sin consumidor validado,
  arriesga drift silencioso entre las claves sembradas y las que el engine use.
  La TABLA se entrega en 44.1; el SEED se hace con el engine. (Consistente con
  las lecciones del repo sobre no crear datos sin consumidor validado.)
- Sin `registry.py` de backend todavía (la ARCH §1 lo lista): no hay router ni
  precedente en otros módulos; se añadirá cuando el módulo tenga endpoints.
- Sin frontend: el registro `investments` en `modules.ts` sigue `enabled:false`
  (se activa en la ARCH fase 40.9).

## Estado del árbol de trabajo y cómo retomar

**Sin commitear** (workflow: commit tras prueba del usuario). `git status`:

```
 M backend/alembic/env.py                    # imports de modelos (metadata completo)
 M backend/tests/conftest.py                 # imports de modelos (create_all)
 M internal_docs/README.md                   # fila Fase 44
 M internal_docs/lessons.md                  # lección: head real del DAG vs filename
?? backend/alembic/versions/aa1b47c9d2e6f0_investment_module_foundations.py
?? backend/app/modules/investment/           # enums + 6 sub-paquetes de modelos
?? backend/tests/test_investment_models.py
?? internal_docs/decisions/0007-investment-global-tables.md
?? internal_docs/improvements/DESIGN-v2-investment-module.md
?? internal_docs/phases/phase-44.1-investment-foundations.md
```

**Ya verificado** (no re-verificar al retomar): `ruff` · `black` · `mypy app/`
(152) · `alembic upgrade/downgrade` reversibles · `alembic check` sin drift ·
11 tests de modelo · 105 tests DB-heavy. Docker + contenedor `postgres` quedaron
levantados durante la verificación.

**Pendiente antes de cerrar la fase**:
- ~~Suite BE completa~~ → hecha el 2026-07-20: **693 passed** de-seleccionando
  `test_ai_*` (requieren Ollama arrancado).
- Commit cuando el usuario dé el OK. Mensaje sugerido:
  `feat(investment): module foundations — enums, models, migration, ADR-0007 — Refs: PHASE-44.1`

**Decisión cerrada** (2026-07-20): el usuario confirma diferir el seed de
`scoring_thresholds` a 44.2 (ver Limitaciones). La TABLA se entrega en 44.1; las
`metric_key` las fija el engine desde el catálogo §5.

## Próxima fase

**PHASE-44.2 (ARCH 40.2)** — el engine puro (sin I/O), fundamento de todo el
análisis. Entregables y puntos de entrada concretos:

- `fundamentals/canonical.py` — dataclass `CanonicalStatement` + enums de
  procedencia (`sourced`/`derived`/`estimated`).
- `analysis/engine/` (PURO, sin I/O):
  - `version.py` — `ENGINE_VERSION = "1.0.0"`.
  - `types.py` — `StatementSeries`, `MetricResult`, `Flag`, `Verdict`, `Provenance`.
  - `conventions.py` — `DAY_COUNT=365`, `avg(t, t−1)`, guardas (equity≤0,
    revenue≤0, ebt≤0, denominador 0), primer año → `status="approximation"`
    (DESIGN §4.5, Dec.3).
  - `derivations.py` — DESIGN §4.4: `total_debt`, `net_debt`, `ebitda`,
    `ebit_clean`, `ebt`, `nopat`, `fcf_cfo`/`fcf_ebitda`, WC dual,
    `maintenance_capex`, `ffo`…
  - `base_ratios.py` — Capa 1 (L*, A*, S*, R*), 28 métricas del catálogo §5.
- **Criterio de salida**: unit tests de las métricas base sobre statements
  sintéticos con importes conocidos (no "≥0"; ver lección PHASE-41 sobre tests
  con importes concretos). El engine es determinista: no toca BD ni red.

Al llegar a **44.4** (adapter EDGAR) hay que PARAR y pedir al usuario el cruzado
de `validate_edgar.py` contra 3 empresas reales antes de fijar el `concept_map`
(ARCH §8). El plan de fases completo está en ARCHITECTURE §9.
