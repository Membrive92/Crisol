# PHASE-44.7 — Módulo de Inversión: persistencia + API + web + móvil

**Estado**: ✅ completada (código verde; sin prueba manual en vivo todavía)
**Rama**: push directo a `main` (flujo del usuario)
**Fecha**: 2026-07-23

## Objetivo

Cerrar el módulo de Inversión de punta a punta sobre el engine puro (44.2-44.5) y
el adapter EDGAR (44.6): persistencia, endpoints, y frontend web + móvil. Al
terminar, un usuario puede ingerir los 10-K de una empresa, obtener el veredicto
forense y llevar una cartera con FIFO — todo desde la app.

Decisión del usuario (2026-07-22): construir **todo el módulo antes de un solo
commit** (contra el "una fase, un commit" del proyecto, aceptado a propósito).

## Decisiones cerradas por el usuario (2026-07-23)

1. **Finnhub sin API key**: el adapter de precios se construye completo y se
   prueba con fixtures; cotizaciones/búsqueda externa DESACTIVADAS hasta que haya
   key (la cartera funciona con datos manuales, valor de mercado "sin cotización").
2. **P&L precio/divisa** (opción A): `price_effect = qty·(p1−p0)·fx_actual`,
   `fx_effect = qty·coste·(fx1−fx0)`. Sin feed FX vivo, `fx_actual = fx_compra` →
   `fx_effect = 0`; la fórmula reparte cuando el feed exista.
3. **Acciones corporativas**: split y stock_dividend se APLICAN (auditado,
   reversible); spinoff/return_of_capital se registran pero aplicar devuelve 400
   (el modelo `ratio` escalar no los expresa).
4. **Dashboard**: Inversión es un espacio SEPARADO, sin reconciliar con el
   patrimonio de Finanzas Domésticas; el `AccountsGuard` se exime en `/investments`
   para que sea accesible sin cuenta de finanzas personales.

## Qué se implementó

**Backend** (todas las tablas ya existían desde 44.1 → cero migraciones nuevas):

- **B1 catálogo**: `catalog/` (search local + `resolve` vía EDGAR + `sic_mapping`).
- **B2 fundamentales**: persistencia (upsert + `is_latest_view`), `restatements.py`
  (divergencia >1% entre filings), ingesta SÍNCRONA por `IngestionJob` (patrón
  `imports`, no BackgroundTask — proxy Next ya a 5 min), 4 endpoints.
- **B3 umbrales**: `thresholds/seed.py` (1440 filas = 12 sectores × 3 normas × 40
  métricas banded; financieras apagan los 8 forenses; IFRS/PGC `uncalibrated`) +
  hash SHA-256 del set resuelto + seed on-startup idempotente.
- **B4 análisis**: builder `FinancialStatement`(BD)→`CanonicalStatement`
  (reconstruye `item_provenance` desde `raw_source_ref`), orquesta las 6 capas,
  serializador genérico dataclass→JSONB, persiste `AnalysisRun`; endpoints run
  (200/409) + histórico.
- **B5 golden**: fixtures reales podadas de MCD/O/JNJ (~950 KB, script
  `prune_edgar_fixtures.py`) + golden test que recorre el pipeline REAL (parser de
  edgartools → engine) y fija invariantes (EBIT sourced/derived, márgenes).
- **B6 cartera**: `fifo.py` (pool global, 409 si vende de más), `corporate_actions.py`,
  dividendos, posiciones derivadas (lotes − allocations); endpoints CRUD.
- **B7 precios**: `PriceAdapter` (Protocol) + `FinnhubAdapter` (mock-tested) +
  refresh on-access TTL + `/portfolio/summary` (§5.1: valor de mercado, P&L
  latente descompuesto, `quote_stale`, posiciones sin cotización fuera de totales).

**Frontend web** (`apps/web`): `packages/types` (modelos+DTOs), `packages/services`
(endpoints/hooks/keys), Tab Análisis (buscador → ingesta → run → informe: veredicto
de 4 preguntas + matriz de seguridad + confianza + paneles forense/calidad/
dividendo), Tab Cartera (KPIs + tabla de posiciones + alta de compra + refresh),
registro `investments` a `enabled`, `AccountsGuard` eximido.

**Frontend móvil** (`apps/mobile`): shell `(modules)/investments` + tabs (Cartera,
Análisis) reutilizando los MISMOS hooks compartidos; pantalla de cartera (KPIs +
posiciones) y de análisis (ticker → ingesta → run → veredicto). Charts pesados
diferidos (como marcó el análisis de scope).

## Verificación

- Backend: **1042 tests passed** (11:40) · ruff · black · mypy (209 files) ·
  `.venv` (Python 3.12, paridad CI).
- Frontend: `pnpm lint` · `pnpm typecheck` · `pnpm test` (web 102 · móvil 18 ·
  services incl. investment) · **knip limpio**.
- [ ] **Prueba manual en vivo pendiente**: levantar la app y hacer el flujo
  ticker→ingesta→análisis→cartera contra la SEC real.

## Limitaciones conocidas / follow-ups

- Sin API key de Finnhub, precios/búsqueda externa desactivados.
- Summary en divisa nativa de cada posición (sin conversión a base con FX vivo).
- Spinoff/return_of_capital: registrar sí, aplicar no (falta modelo).
- Charts del informe (evolución/stress/common-size) y paridad móvil completa del
  informe: diferidos.
- Sin tests de componente FE específicos del módulo (la lógica está cubierta en
  backend + services); follow-up.
- El commit incluye también el adapter EDGAR de 44.6c (estaba sin commitear).
