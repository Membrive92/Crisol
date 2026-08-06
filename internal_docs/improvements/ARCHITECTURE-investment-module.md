# ARCHITECTURE — Módulo de Inversión (spec de implementación)

**Estado**: 🏗️ arquitectura de implementación
**Audiencia**: modelo implementador (Claude Code / Opus). Este documento
es la fuente de verdad para implementar. Ante ambigüedad, prevalece lo
aquí escrito; ante hueco, preguntar al usuario antes de improvisar.
**Documentos padre**: `DESIGN-v2-investment-module.md` (diseño lógico,
modelo canónico, catálogo de métricas, 18 decisiones confirmadas).
Este documento NO redefine métricas ni fórmulas — las referencia.
**Convenciones de repo**: aplican las reglas de `CLAUDE.md` del monorepo
Crisol y los patrones existentes de `backend/app/modules/personal_finance/*`
(módulos con `models/schemas/repository/service/router`, Alembic,
Pydantic v2, Decimal en importes, tests pytest, docs de fase).

---

## 0. Principios de implementación (no negociables)

1. **Motor de cálculo puro.** Todo el cálculo financiero vive en
   `analysis/engine/` como funciones puras: entran dataclasses/objetos
   inmutables, salen resultados. **Cero I/O, cero acceso a BD, cero
   datetime.now()** dentro del engine. La fecha de referencia entra
   como parámetro. Esto hace el engine testeable con goldens y
   versionable con `ENGINE_VERSION`.
2. **Ingesta separada de cálculo.** El pipeline de ingesta
   (descarga → cache → normalización → persistencia) nunca calcula
   métricas. El engine nunca descarga nada.
3. **Decimal en todo el pipeline.** Ningún float en importes o ratios
   persistidos. Los ratios se calculan en Decimal y solo se convierten
   en la capa de presentación.
4. **Huecos explícitos.** Una partida no disponible es `None`, jamás
   `0`. Las funciones del engine deben tolerar `None` y propagar
   "métrica no calculable" con la razón, nunca lanzar excepción por
   dato ausente ni calcular con ceros silenciosos.
5. **Nada de lógica en el router.** Router → service → repository /
   engine. Igual que el resto de Crisol.
6. **El usuario final es single-user local-first**, pero el código
   respeta el patrón multi-tenant del repo salvo en las tablas
   declaradas globales (ver §2.1, ADR).

---

## 1. Estructura de paquetes

```
backend/app/modules/investment/
  __init__.py
  registry.py                    # metadatos del módulo
  catalog/                       # Security (compartido por ambas tabs)
    models.py schemas.py repository.py service.py router.py
    sic_mapping.py               # SIC code → sector interno (Dec.15)
  portfolio/                     # Tab Cartera
    models.py                    # Lot, Sale, DividendReceived,
                                 # CorporateAction, LotAdjustment
    schemas.py repository.py service.py router.py
    fifo.py                      # matching FIFO global por security (Dec.10)
    corporate_actions.py         # aplicación auditada (Dec.9)
  fundamentals/                  # ingesta de estados financieros
    models.py                    # FinancialStatement, RestatementFlag,
                                 # IngestionJob
    schemas.py repository.py service.py router.py
    canonical.py                 # dataclass CanonicalStatement + enums
                                 #   de procedencia (sourced/derived/estimated)
    adapters/
      base.py                    # Protocol FundamentalsAdapter
      edgar.py                   # implementación EDGAR (edgartools)
      concept_map.py             # mapeo XBRL us-gaap → canónico
    normalization.py             # adapter output → CanonicalStatement
    validation.py                # cuadres, signos, tests de propiedad (Dec.18)
    cache.py                     # cache local de filings crudos (Dec.18)
    restatements.py              # detección de divergencias entre filings (Dec.6)
  analysis/
    models.py                    # AnalysisRun
    schemas.py repository.py service.py router.py
    engine/                      # ★ PURO — sin I/O
      __init__.py
      version.py                 # ENGINE_VERSION = "1.0.0"
      types.py                   # StatementSeries, MetricResult,
                                 #   Flag, Verdict, Provenance
      conventions.py             # DAY_COUNT=365, avg(t,t-1), primer año
      derivations.py             # §4.4 del DESIGN (total_debt, ebt,
                                 #   fcf_cfo, fcf_ebitda, WC dual...)
      base_ratios.py             # Capa 1 (L*, A*, S*, R*)
      evolution.py               # Capa 1.5 (horizontal, vertical,
                                 #   reglas de coherencia)
      forensic.py                # Capa 2 (M, Z/Z'', F, accruals, F5, F6)
      dividend.py                # Capa 3 (D*, Q*, B*, T*)
      stress.py                  # Capa 3.5 (shocks paramétricos)
      synthesis.py               # Capa 4 (matriz de banderas, veredicto,
                                 #   confianza, staleness)
  pricing/                       # cotizaciones (staleness-tolerant)
    models.py                    # PriceQuote
    schemas.py repository.py service.py router.py
    adapters/
      base.py                    # Protocol PriceAdapter — SOLO quotes:
                                 #   async quotes(symbols) ->
                                 #     dict[sym, Quote | QuoteError]
                                 #   symbol_search NO vive aquí (ADR-0008:
                                 #   catalog/adapters/symbol_search/).
                                 #   Quote lleva `currency` DEL PROVEEDOR
                                 #   (PHASE-44.11 D4): se persiste esa, no
                                 #   la del catálogo; discrepancia con
                                 #   Security.currency → quality flag
      yfinance.py                # PRIMARIO multi-mercado (US+LSE+BME+
                                 #   XETRA+Euronext, sufijos Yahoo). NO
                                 #   oficial: throttling ~1 req/s, batch.
                                 #   ★ Normaliza GBp/GBX→GBP (÷100;
                                 #   currency SIEMPRE ISO real)
      finnhub.py                 # Convive tras selector PRICE_PROVIDER
                                 #   (default yfinance). US-only: símbolo
                                 #   sin cobertura → exclusión estándar
                                 #   "sin cotización", nunca error
      eodhd.py                   # fallback de pago documentado (All-World
                                 #   19,99 €/mes) — NO implementar salvo
                                 #   rotura recurrente de yfinance
                                 # FX: NO es adapter de pricing. Se consume
                                 #   el módulo transversal `currency`
                                 #   (exchange_rates, BCE — PHASE-44.11 D1)
    refresh.py                   # política TTL + refresh on-access
  thresholds/
    models.py                    # ScoringThresholds (Dec.8)
    seed.py                      # seed inicial sector × norma
    repository.py service.py
```

Frontend:

```
apps/web/app/(app)/investment/
  layout.tsx                     # tabs Cartera | Análisis
  portfolio/page.tsx
  analysis/page.tsx              # buscador + lista de análisis previos
  analysis/[securityId]/page.tsx # informe del último run
  analysis/[securityId]/runs/[runId]/page.tsx
apps/web/components/investment/
  security-search.tsx
  portfolio/{lots-table,lot-form,sales-table,dividends-table,
             corporate-actions-panel,position-summary}.tsx
  analysis/{ingestion-status,statement-viewer,evolution-view,
            scores-panel,dividend-panel,stress-panel,verdict-card,
            completeness-badge,runs-history}.tsx
packages/types/src/models/investment.ts
packages/types/src/dto/investment.dto.ts
packages/services/src/api/endpoints/investment.ts
packages/services/src/query/hooks/useInvestment*.ts
```

Registro del módulo: `packages/types/src/registry/modules.ts` — el
módulo "Inversión" existe como locked/PRONTO; pasar a `enabled` cuando
la Tab Análisis tenga MVP funcional (no antes).

---

## 2. Modelo de datos (DDL-nivel)

### 2.1. Tablas globales (sin `user_id`) — ADR obligatorio

`securities`, `financial_statements`, `restatement_flags`,
`scoring_thresholds` son **globales** [Dec.11]. Escribir
`internal_docs/decisions/000X-investment-global-tables.md` en la
primera fase declarando la excepción al patrón multi-tenant y su
razón (los datos de mercado/regulatorios son objetivos; duplicarlos
por usuario no tiene sentido). Los repositorios de estas tablas NO
filtran por usuario; los tests no deben inyectar `user_id` en ellas.

### 2.2. Esquema

```sql
-- ─── catálogo (global) ───
CREATE TABLE securities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker VARCHAR(12) NOT NULL,
  exchange VARCHAR(16) NOT NULL,
  name TEXT NOT NULL,
  cik VARCHAR(10),                    -- zero-padded
  isin VARCHAR(12),
  sector sector_internal NOT NULL DEFAULT 'unknown',
  accounting_std accounting_std NOT NULL,   -- 'GAAP'|'IFRS'|'PGC'
  currency CHAR(3) NOT NULL,
  security_type security_type NOT NULL DEFAULT 'STOCK',
  is_financial BOOLEAN NOT NULL DEFAULT FALSE,
  is_reit BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
  UNIQUE (ticker, exchange)
);
CREATE INDEX ix_securities_cik ON securities(cik) WHERE cik IS NOT NULL;

-- ─── fundamentales (global) ───
CREATE TABLE financial_statements (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  security_id UUID NOT NULL REFERENCES securities(id) ON DELETE CASCADE,
  fiscal_year INT NOT NULL,
  fiscal_year_end DATE NOT NULL,             -- Dec.12
  period_type period_type NOT NULL DEFAULT 'ANNUAL',
  filing_accession VARCHAR(25) NOT NULL,     -- Dec.6 (clave de versión)
  is_latest_view BOOLEAN NOT NULL DEFAULT FALSE,
  filing_date DATE NOT NULL,
  source statement_source NOT NULL,          -- 'EDGAR_XBRL'|'MANUAL'
  accounting_std accounting_std NOT NULL,
  currency CHAR(3) NOT NULL,
  -- Partidas canónicas §4 del DESIGN. TODAS NUMERIC(20,4) NULL.
  cash NUMERIC(20,4), current_financial_assets NUMERIC(20,4),
  receivables NUMERIC(20,4), inventory NUMERIC(20,4),
  current_assets NUMERIC(20,4), ppe_net NUMERIC(20,4),
  goodwill NUMERIC(20,4), intangibles NUMERIC(20,4),
  deferred_tax_assets NUMERIC(20,4), total_assets NUMERIC(20,4),
  short_term_debt NUMERIC(20,4), ltd_current_portion NUMERIC(20,4),
  accounts_payable NUMERIC(20,4),
  lease_liabilities_current NUMERIC(20,4),
  current_liabilities NUMERIC(20,4), long_term_debt NUMERIC(20,4),
  lease_liabilities_noncurrent NUMERIC(20,4),
  deferred_tax_liabilities NUMERIC(20,4), total_liabilities NUMERIC(20,4),
  share_premium NUMERIC(20,4), retained_earnings NUMERIC(20,4),
  treasury_stock NUMERIC(20,4), equity NUMERIC(20,4),
  revenue NUMERIC(20,4), cogs NUMERIC(20,4), sga_expense NUMERIC(20,4),
  rd_expense NUMERIC(20,4), depreciation_amortization NUMERIC(20,4),
  impairments NUMERIC(20,4), gains_on_sale_of_business NUMERIC(20,4),
  ebit NUMERIC(20,4), interest_expense NUMERIC(20,4),
  taxes NUMERIC(20,4), net_income NUMERIC(20,4),
  shares_basic NUMERIC(20,4), shares_diluted NUMERIC(20,4),
  shares_outstanding_eop NUMERIC(20,4), sbc_expense NUMERIC(20,4),
  cfo NUMERIC(20,4), wc_change_inventory NUMERIC(20,4),
  capex NUMERIC(20,4), acquisitions NUMERIC(20,4),
  divestitures NUMERIC(20,4), dividends_paid NUMERIC(20,4),
  buybacks NUMERIC(20,4), share_issuance NUMERIC(20,4),
  debt_change NUMERIC(20,4), taxes_paid NUMERIC(20,4),
  raw_source_ref JSONB NOT NULL DEFAULT '{}',   -- Dec.13: originales sin colapsar
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE (security_id, fiscal_year, period_type, filing_accession)
);
CREATE INDEX ix_fs_latest
  ON financial_statements(security_id, fiscal_year)
  WHERE is_latest_view;

CREATE TABLE restatement_flags (                -- Dec.6
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  security_id UUID NOT NULL REFERENCES securities(id) ON DELETE CASCADE,
  fiscal_year INT NOT NULL,
  filing_a VARCHAR(25) NOT NULL, filing_b VARCHAR(25) NOT NULL,
  divergences JSONB NOT NULL,   -- [{item, value_a, value_b, pct}]
  detected_at TIMESTAMPTZ NOT NULL,
  UNIQUE (security_id, fiscal_year, filing_a, filing_b)
);

CREATE TABLE ingestion_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  security_id UUID NOT NULL REFERENCES securities(id),
  user_id UUID NOT NULL,                        -- quien la pidió (auditoría)
  status job_status NOT NULL DEFAULT 'pending', -- pending|running|done|failed
  params JSONB NOT NULL,                        -- {filings_back: 5}
  progress JSONB NOT NULL DEFAULT '{}',         -- {step, filings_done, total}
  error TEXT,
  created_at TIMESTAMPTZ NOT NULL, finished_at TIMESTAMPTZ
);

-- ─── umbrales (global) ─── Dec.8
CREATE TABLE scoring_thresholds (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sector sector_internal NOT NULL,
  accounting_std accounting_std NOT NULL,
  metric_key VARCHAR(64) NOT NULL,
  direction threshold_direction NOT NULL,   -- lower_better|higher_better|band
  low_alarm NUMERIC(12,6), low_ok NUMERIC(12,6),
  high_ok NUMERIC(12,6), high_alarm NUMERIC(12,6),
  model_variant VARCHAR(32),
  applies BOOLEAN NOT NULL DEFAULT TRUE,
  UNIQUE (sector, accounting_std, metric_key)
);

-- ─── cartera (scoped por usuario) ───
CREATE TABLE inv_lots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  security_id UUID NOT NULL REFERENCES securities(id),
  account_id UUID NULL REFERENCES accounts(id) ON DELETE SET NULL, -- Dec.10
  trade_date DATE NOT NULL,
  quantity NUMERIC(20,8) NOT NULL CHECK (quantity > 0),
  price NUMERIC(20,6) NOT NULL,
  fx_rate_at_trade NUMERIC(16,8) NOT NULL DEFAULT 1,
  fees NUMERIC(12,4) NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX ix_lots_user_sec ON inv_lots(user_id, security_id, trade_date);

CREATE TABLE inv_sales (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  security_id UUID NOT NULL REFERENCES securities(id),
  trade_date DATE NOT NULL,
  quantity NUMERIC(20,8) NOT NULL CHECK (quantity > 0),
  price NUMERIC(20,6) NOT NULL,
  fx_rate_at_trade NUMERIC(16,8) NOT NULL DEFAULT 1,
  fees NUMERIC(12,4) NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE inv_sale_allocations (       -- resultado del matching FIFO
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sale_id UUID NOT NULL REFERENCES inv_sales(id) ON DELETE CASCADE,
  lot_id UUID NOT NULL REFERENCES inv_lots(id),
  quantity NUMERIC(20,8) NOT NULL,
  cost_basis NUMERIC(20,6) NOT NULL,      -- en divisa nativa
  cost_basis_fx NUMERIC(16,8) NOT NULL    -- fx del lote (Dec: P&L precio vs divisa)
);

CREATE TABLE inv_dividends_received (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  security_id UUID NOT NULL REFERENCES securities(id),
  ex_date DATE, pay_date DATE NOT NULL,
  gross_amount NUMERIC(14,4) NOT NULL,
  withholding_tax NUMERIC(14,4) NOT NULL DEFAULT 0,
  net_amount NUMERIC(14,4) NOT NULL,
  currency CHAR(3) NOT NULL, fx_rate NUMERIC(16,8) NOT NULL DEFAULT 1,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE inv_corporate_actions (      -- Dec.9
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  security_id UUID NOT NULL REFERENCES securities(id),
  action_type corp_action_type NOT NULL,  -- split|spinoff|stock_dividend|return_of_capital
  action_date DATE NOT NULL,
  ratio NUMERIC(16,8),                    -- ej. split 4:1 → 4
  notes TEXT,
  applied_at TIMESTAMPTZ,                 -- NULL = registrada, no aplicada
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE inv_lot_adjustments (        -- rastro de auditoría (Dec.9)
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  corporate_action_id UUID NOT NULL REFERENCES inv_corporate_actions(id),
  lot_id UUID NOT NULL REFERENCES inv_lots(id),
  field VARCHAR(16) NOT NULL,             -- quantity|price
  old_value NUMERIC(20,8) NOT NULL, new_value NUMERIC(20,8) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);

-- ─── precios (global; cache de cotizaciones) ───
CREATE TABLE price_quotes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  security_id UUID NOT NULL REFERENCES securities(id) ON DELETE CASCADE,
  price NUMERIC(20,6) NOT NULL,
  prev_close NUMERIC(20,6),            -- para daily change
  currency CHAR(3) NOT NULL,
  as_of TIMESTAMPTZ NOT NULL,          -- timestamp del dato según proveedor
  fetched_at TIMESTAMPTZ NOT NULL,     -- cuándo lo trajimos (TTL)
  provider VARCHAR(24) NOT NULL,       -- 'finnhub'|...
  UNIQUE (security_id)                 -- una fila viva por security;
                                       -- histórico de precios NO es objetivo
);

-- FX: SIN tabla propia (superseded — PHASE-44.11 D1). Única fuente de
-- tipos de la aplicación = `exchange_rates` del módulo transversal
-- `currency` (datos BCE vía Frankfurter, cron nocturno PHASE-11.1,
-- `ensure_rates_for_dates` + `rate_date` en el resultado). El módulo
-- investment la consume vía `currency.service`, nunca directamente.

-- ─── análisis (scoped) ─── Dec.7
CREATE TABLE analysis_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  security_id UUID NOT NULL REFERENCES securities(id),
  user_id UUID NOT NULL,
  run_date TIMESTAMPTZ NOT NULL,
  engine_version VARCHAR(16) NOT NULL,
  thresholds_version VARCHAR(64) NOT NULL, -- hash del set de umbrales usado
  years_covered INT[] NOT NULL,
  -- primer nivel en columnas (consultable en serie):
  m_score NUMERIC(10,4), z_score NUMERIC(10,4), z_variant VARCHAR(16),
  f_score SMALLINT, accruals_ratio NUMERIC(10,6),
  fcf_payout NUMERIC(10,6), fcf_coverage NUMERIC(10,4),
  dividend_verdict VARCHAR(16),           -- healthy|caution|stressed|not_applicable
  confidence NUMERIC(5,4) NOT NULL,
  -- desglose:
  scores_detail JSONB NOT NULL, dividend_analysis JSONB NOT NULL,
  evolution JSONB NOT NULL, flags JSONB NOT NULL,
  verdict JSONB NOT NULL, data_completeness JSONB NOT NULL
);
CREATE INDEX ix_runs_sec_user ON analysis_runs(security_id, user_id, run_date DESC);
```

**Notas de implementación**:
- `Position` NO es tabla: es agregado derivado (query sobre lots −
  allocations). Evita el clásico bug de desincronización.
- `NUMERIC(20,4)` en partidas: los filings reportan en unidades o
  miles; se persisten SIEMPRE en unidades absolutas de la divisa
  (normalizar el `scale` XBRL en ingesta).
- Enums Postgres nativos para `sector_internal`, `accounting_std`,
  `period_type`, `statement_source`, `job_status`,
  `threshold_direction`, `corp_action_type`, `security_type`.

---

## 3. Pipeline de ingesta (fundamentals)

### 3.1. Contrato del adapter

```python
# fundamentals/adapters/base.py
class RawFilingData(TypedDict):
    accession: str
    filing_date: date
    fiscal_year: int
    fiscal_year_end: date
    facts: dict[str, Decimal | None]   # concepto fuente → valor (unidades absolutas)
    raw: dict                          # payload completo para raw_source_ref

class FundamentalsAdapter(Protocol):
    async def resolve(self, ticker: str) -> SecurityIdentity: ...
    async def list_annual_filings(self, identity, limit: int) -> list[FilingRef]: ...
    async def fetch_filing(self, ref: FilingRef) -> RawFilingData: ...
```

### 3.2. EdgarAdapter

- Dependencia: `edgartools` **pineada** en `pyproject/requirements`
  (fijar la versión que valide el usuario en el cruzado; anotar en el
  commit). Identidad SEC vía env `EDGAR_IDENTITY="Nombre email"` —
  obligatoria, fallar en arranque del servicio con mensaje claro si
  falta al intentar ingerir.
- Red: requiere `data.sec.gov` y `www.sec.gov` accesibles desde el
  backend local del usuario. Rate limit SEC ~10 req/s: serializar
  descargas (no paralelizar filings) [Dec.18].
- **Cache**: `fundamentals/cache.py` guarda el payload crudo por
  `(cik, accession)` en disco (`backend/data/edgar_cache/` —
  configurable por env, excluido de git). Toda petición pasa por la
  cache primero. La cache es evidencia de auditoría: si edgartools
  cambia su normalización entre versiones, el crudo permite re-derivar.
- `concept_map.py`: dict canónico → lista ordenada de conceptos
  us-gaap candidatos (partir de la lista de `validate_edgar.py`
  ampliada según el cruzado del usuario). Primer concepto con dato
  gana. Registrar en `raw_source_ref.mapping` qué concepto alimentó
  cada partida canónica.

### 3.3. Normalización y signos

`normalization.py` produce `CanonicalStatement` desde `RawFilingData`:
- Aplicar `scale`/`decimals` XBRL → unidades absolutas.
- **Ausencia vs cero — `IMPUTABLE_ZERO_CONCEPTS`** (decisión de
  diseño, DESIGN §4.5): concepto ausente en el filing → `Decimal(0)`
  con proveniencia `imputed_zero` SOLO si está en esta lista:
  `short_term_debt, ltd_current_portion, lease_liabilities_current,
  lease_liabilities_noncurrent, current_financial_assets, inventory,
  goodwill, intangibles, deferred_tax_assets, deferred_tax_liabilities,
  treasury_stock, share_premium, rd_expense, sbc_expense, impairments,
  gains_on_sale_of_business, acquisitions, divestitures, buybacks,
  share_issuance, dividends_paid, debt_change, wc_change_inventory`.
  El resto de partidas ausentes → `None` (nunca 0).
  **Condicional**: `interest_expense` ausente → 0 solo si
  short_term_debt + ltd_current_portion + long_term_debt es 0 (real o
  imputado); con deuda > 0 → `None`.
  Registrar cada imputación en `raw_source_ref.mapping` con marca
  `imputed_zero`. Si una imputación rompe un cuadre de
  `validation.py` (componentes > total), revertir a `None` + quality
  flag: la identidad contable manda sobre la lista.
- **Convención de signos canónica**: todas las partidas se almacenan
  en positivo con semántica fija (capex positivo = inversión;
  dividends_paid positivo = pago; buybacks positivo = recompra).
  Documentar en docstring de `canonical.py`. Los conceptos XBRL con
  signo inconsistente entre empresas se normalizan aquí.
- `validation.py` — tests de propiedad por statement [Dec.18]:
  `|total_assets − (total_liabilities + equity)| / total_assets < 0.01`;
  márgenes en [-1, 1] salvo flag; `current_assets ≥ cash`; etc. Fallo
  → `quality_flags` en el statement, NO aborta la ingesta.

### 3.4. Versionado y restatements

Al persistir un filing con comparativos: cada año que trae se inserta
como fila propia con su `filing_accession`. `restatements.py` compara
partidas del mismo `(security, fiscal_year)` entre filings distintos;
divergencia relativa > 1% en partidas clave → `RestatementFlag`.
Recalcular `is_latest_view`: para cada año, la versión del filing con
`filing_date` más reciente.

### 3.5. Job de ingesta

La descarga de 4-5 filings tarda 30-90 s. Endpoint `POST .../ingest`
crea `IngestionJob` y lanza FastAPI `BackgroundTask` (suficiente para
single-user local; no introducir cola externa). El frontend hace
polling de `GET /investment/fundamentals/jobs/{id}` y muestra
`progress`. Reintentos: no automáticos; el job falla con `error`
legible y el usuario relanza.

---

## 4. Engine de análisis

### 4.1. Tipos

```python
# engine/types.py
@dataclass(frozen=True)
class StatementSeries:
    security: SecuritySnapshot            # sector, std, is_reit, is_financial
    statements: tuple[CanonicalStatement, ...]  # orden ascendente por año,
                                                # solo is_latest_view
    as_of: date                                 # fecha de referencia (staleness)

@dataclass(frozen=True)
class MetricResult:
    key: str
    value: Decimal | None
    status: Literal["ok","not_computable","approximation"]
    reason: str | None                    # por qué no computable
    provenance: Provenance                # sourced/derived/estimated/imputed_zero
    band: Literal["healthy","caution","stressed"] | None

@dataclass(frozen=True)
class Flag:
    key: str; severity: Literal["info","amber","red"]
    message: str                          # lenguaje de negocio, español
    evidence: dict                        # serie/valores de soporte
```

### 4.2. Orquestación

```python
# analysis/service.py (pseudocódigo del run)
series = build_series(security_id)            # repo → StatementSeries
thresholds = load_thresholds(sector, std)     # + hash → thresholds_version
r1  = base_ratios.compute(series, thresholds)
r15 = evolution.compute(series, thresholds)
r2  = forensic.compute(series, thresholds)    # respeta applies/model_variant
r3  = dividend.compute(series, thresholds)    # FFO si is_reit
r35 = stress.compute(series, params)          # shocks del request o defaults
verdict = synthesis.compute(r1, r15, r2, r3, r35, series)
persist AnalysisRun(engine_version=ENGINE_VERSION, thresholds_version=hash, ...)
```

Reglas duras del engine:
- `is_financial=True` → `forensic.compute` devuelve M/Z como
  `not_computable` con `reason="modelo no aplicable a financieras"`.
  Nunca omite la clave: el frontend muestra el porqué.
- Denominadores medios: `conventions.avg_balance(series, item, year)`
  — media (t,t−1); primer año → EOP + `status="approximation"` [Dec.3].
- Divergencia `fcf_cfo` vs `fcf_ebitda` > 15% sostenida 2 años →
  `Flag(key="fcf_divergence", severity="amber")`.
- Todas las fórmulas: referenciar el DESIGN v2 §5 en docstrings con la
  clave de métrica (L1, S4b, D5, Q3, T2...). No inventar métricas ni
  umbrales fuera del catálogo.

### 4.3. Versionado

`ENGINE_VERSION` (semver) se incrementa con cualquier cambio de fórmula
o incorporación de métrica. `thresholds_version` = hash SHA-256 del set
de umbrales cargado (orden canónico). Ambos van al run [Dec.7]. Test
que falla si se cambia una fórmula sin tocar la versión: golden test
(ver §7).

---

## 5. API

Prefijo `/investment`. Todos los endpoints scoped por usuario
autenticado salvo lectura de catálogo global.

> **Corregido en PHASE-44.8 (ADR-0008).** El buscador de tres pasos que se
> describía aquí no es implementable tal cual: el `/search` de Finnhub **no
> devuelve la bolsa** (sus únicos campos son `description`, `displaySymbol`,
> `symbol` y `type`), así que `symbol_search` del `PriceAdapter` no puede alimentar
> un buscador multi-mercado — se retiró sin haber tenido consumidor. Y que el
> cliente aporte el `exchange` duplicaba filas contra la restricción única
> `(ticker, exchange)`. El diseño vigente es local-first y el mercado lo decide el
> servidor; ver [ADR-0008](../decisions/0008-investment-symbol-search.md) y el plan
> [`phase-44.8-investment-search-hybrid.md`](phase-44.8-investment-search-hybrid.md).

```
# catálogo — buscador local-first (ADR-0008)
GET  /investment/securities/search?q=&intent=analysis|portfolio
     → 1) catálogo local (ticker, nombre, CIK)
       2) índice en memoria de los emisores de la SEC (sin red, sin key)
       3) SÓLO con intent=portfolio y proveedor externo activo (apagado por
          defecto): capa multi-mercado on-demand, marcada `in_catalog: false`
       Cada hit declara su capacidad (analizable / sólo cartera) ANTES del clic.
POST /investment/securities/adopt     {listing_key}   # Entrega 2
POST /investment/securities/resolve   {ticker, exchange?}  # deprecado
     → `exchange` es opcional y NO vinculante: el servidor normaliza la plaza
       y deduplica por `(cik, ticker)`, no por la clave de la tabla.
GET  /investment/securities/{id}

# precios
POST /investment/pricing/refresh      {security_ids?: [] | all_portfolio}
     → fuerza refresh ignorando TTL (botón manual en UI)
# No hay GET de quote suelto: las cotizaciones viajan embebidas en
# /portfolio/summary y /securities/{id}. Refresh implícito on-access
# si fetched_at > TTL (ver §8).

# fundamentales
POST /investment/fundamentals/{security_id}/ingest   {filings_back: int=5}
     → 202 {job_id}
GET  /investment/fundamentals/jobs/{job_id}
GET  /investment/fundamentals/{security_id}/statements?view=latest|all
GET  /investment/fundamentals/{security_id}/restatements

# análisis
POST /investment/analysis/{security_id}/run
     {stress_params?: {revenue_shock_pct?, rate_shock_bps?,
                       pct_variable_debt?}}
     → 200 AnalysisRunRead (síncrono: el cálculo es <1s con datos ya
       ingeridos; si no hay statements → 409 con instrucción de ingerir)
GET  /investment/analysis/{security_id}/runs          (histórico)
GET  /investment/analysis/runs/{run_id}

# cartera
POST/GET/DELETE /investment/portfolio/lots
POST/GET/DELETE /investment/portfolio/sales           (POST ejecuta FIFO
                                                        y crea allocations;
                                                        409 si qty > held)
POST/GET/DELETE /investment/portfolio/dividends
POST /investment/portfolio/corporate-actions           (registra)
POST /investment/portfolio/corporate-actions/{id}/apply (aplica auditado)
GET  /investment/portfolio/summary
```

### 5.1. Contrato de `/portfolio/summary` (métricas de broker)

Set estándar IBKR-like, todo computable con quotes EOD/1h (ningún
dato intradía requerido). Por posición:

| Campo | Cálculo |
|---|---|
| quantity | Σ lots − Σ allocations |
| avg_cost (nativa y EUR) | coste ponderado de lots abiertos; EUR con fx_rate_at_trade |
| cost_basis | quantity × avg_cost (+fees prorrateadas) |
| last_price, quote_as_of, quote_stale | de price_quotes; `quote_stale=true` si fetched_at > TTL y el refresh falló |
| market_value (nativa y EUR) | quantity × last_price; EUR vía el servicio transversal `currency` (`exchange_rates`, datos BCE, única fuente de tipos de la app — PHASE-44.11 D1) con el `rate_date` aplicado visible en el payload |
| unrealized_pnl / unrealized_pnl_pct | market_value − cost_basis, **descompuesto en price_effect y fx_effect** (regla §3.2 del DESIGN) |
| daily_change / daily_change_pct | quantity × (last_price − prev_close) |
| realized_pnl | Σ de inv_sale_allocations (FIFO) |
| dividends_received_total / _ttm | Σ inv_dividends_received (neto y bruto) |
| yield_on_cost | dividends_ttm_gross / cost_basis |
| total_return | unrealized + realized + dividends_net |
| weight_pct | market_value / total del portfolio |

Nivel cartera: total_market_value, total_cost_basis, total_unrealized
(price/fx separados), total_realized, dividends_ytd y _ttm,
daily_pnl, exposición por divisa (% USD/EUR/…), exposición por sector
(desde securities.sector), top-5 posiciones por peso.

Si una posición no tiene quote (proveedor sin cobertura del ticker):
market_value = null, la posición se lista con badge "sin cotización"
y se EXCLUYE de los totales — mismo principio anti-dato-ficticio de
`is_unvalued` en PHASE-31.4. Nunca valorar a coste como fallback
silencioso.

Errores: seguir el patrón de HTTPException del repo con `detail` en
español, accionable ("No hay estados financieros ingeridos para KO.
Lanza la ingesta primero.").

---

## 6. Frontend (contratos, no diseño visual)

- **Tabs** en `layout.tsx`: Cartera | Análisis. Desacopladas: ninguna
  importa lógica de la otra; comparten `useSecuritySearch`.
- **Flujo Análisis**: buscador → si el security no tiene statements →
  CTA "Descargar 10-K (EDGAR)" → `ingestion-status` con polling →
  al completar, botón "Ejecutar análisis" → informe.
- **Informe** (orden de lectura): `verdict-card` (4 preguntas del
  dividendo + confianza + staleness) → `scores-panel` (M/Z/F/accruals
  con banda y "no aplicable" explicado) → `dividend-panel` (cobertura,
  calidad de caja, trayectoria; toggles D1/D4/D5/D6) → `stress-panel`
  (inputs de shock editables, margen de seguridad de ingresos,
  etiqueta "escenario hipotético" SIEMPRE visible) → `evolution-view`
  (statement común-size con años en columnas, heatmap de Δ%, top
  movers, flags de coherencia) → `statement-viewer` (canónico +
  toggle a raw_source_ref) → `completeness-badge` + `runs-history`.
- **Formato numérico**: tabular-nums; ratios con 2 decimales;
  importes con separador es-ES; nunca mostrar `-0,00`.
- Tokens de diseño y patrones de DESIGN.md del repo (copper, sin
  shadows, `*-soft` para chips). Nada de librerías UI nuevas.

---

## 7. Testing

| Nivel | Qué | Cómo |
|---|---|---|
| Engine unit | Cada métrica del catálogo | Statements sintéticos mínimos; casos: valor esperado, `None` en input → `not_computable` con reason, primer año → `approximation`, guards (equity≤0) |
| Engine golden | Regresión de fórmulas | 2-3 empresas reales: fixtures JSON de facts EDGAR cacheados en `backend/tests/fixtures/edgar/` (comprimidos). Golden = AnalysisRun serializado. Cambio de output sin bump de `ENGINE_VERSION` → test falla |
| Normalización | Propiedades | Cuadre de balance, signos canónicos, escala absoluta — sobre los mismos fixtures |
| Restatements | Divergencia detectada | Fixture con dos filings del mismo año con cifras distintas |
| FIFO | Matching y P&L | Compra-venta parcial multi-lote; venta > held → 409; corporate action split 4:1 → cantidades/precios ajustados con `lot_adjustments` y FIFO posterior correcto |
| API | Contratos | Ingesta 202+job, run 409 sin datos, run 200 con datos, scoping usuario en tablas scoped |
| Adapter | Solo integración manual | El adapter EDGAR NO se testea contra red en CI: se testea contra fixtures. Un script manual (`scripts/edgar_smoke.py`) para verificación en vivo |

Sin mocks de red en unit tests del engine: el engine no tiene red por
construcción (§0.1). Los fixtures reales se capturan una vez con la
cache de §3.2.

---

## 8. Configuración y entorno

| Variable | Uso | Default |
|---|---|---|
| `EDGAR_IDENTITY` | Header SEC "Nombre email" | — (obligatoria para ingerir) |
| `EDGAR_CACHE_DIR` | Cache de filings crudos | `backend/data/edgar_cache` |
| `EDGAR_FILINGS_BACK` | Filings por defecto | 5 |
| `PRICE_PROVIDER` | Adapter de precios activo | `finnhub` |
| `FINNHUB_API_KEY` | Key del proveedor | — (obligatoria para quotes/search externo) |
| `PRICE_TTL_HOURS` | Frescura máxima antes de refresh on-access | `24` (poner `1` para refresco horario) |

### 8.1. Política de precios (staleness-tolerant, decisión del usuario)

**No hay tiempo real ni lo habrá** (regulado, de pago, innecesario
para trazabilidad). Google Finance queda **descartado como fuente**:
su API fue descontinuada en 2012 y no existe acceso programático
oficial — solo la función de Sheets o scraping (frágil, ToS). El
requisito real (refresco 1h/diario) se cubre con API oficial gratuita.

Mecánica:
1. **Refresh on-access con TTL**: al pedir `/portfolio/summary` o
   `/securities/{id}`, las quotes con `fetched_at` más viejo que
   `PRICE_TTL_HOURS` se refrescan en la misma request (serializado,
   respetando el rate limit del proveedor — Finnhub free: 60 req/min,
   sobrado para <60 posiciones). Sin scheduler ni cron: local-first,
   la app solo necesita precios cuando alguien mira.
2. **Refresh manual**: botón en UI → `POST /pricing/refresh`.
3. **Fallo de proveedor**: se sirve la última quote con
   `quote_stale=true` y timestamp visible. Nunca se bloquea la vista
   de cartera por un proveedor caído.
4. La UI muestra SIEMPRE `quote_as_of` ("precios a cierre de ayer" /
   "hace 2 h") — coherente con la política de staleness del análisis.

`PriceAdapter` es Protocol (como `FundamentalsAdapter`): cambiar de
proveedor = un adapter nuevo. Finnhub MVP (quotes con prev_close +
symbol search multi-exchange en free tier); Twelve Data candidata
para cobertura EU futura.

Seed de `scoring_thresholds`: `thresholds/seed.py` puebla el set
US-GAAP × sectores internos con los umbrales del DESIGN v2 §5
(constantes nombradas, una fila por métrica/sector donde difiera del
genérico). IFRS/PGC: filas con `applies=false` o cutoffs marcados
`model_variant='uncalibrated'` hasta calibración (riesgo abierto del
DESIGN).

---

## 9. Secuencia de implementación (fases)

Numeración orientativa PHASE-40.x — ajustar al índice real del repo.
Cada fase entregable e independiente, con sus tests verdes antes de
avanzar. **No adelantar fases**: la tentación de tocar frontend antes
de que el engine esté golden-tested produce retrabajo.

| Fase | Contenido | Criterio de salida |
|---|---|---|
| 40.1 | Migraciones completas + enums + ADR tablas globales + modelos SQLAlchemy + seed thresholds | `alembic upgrade/downgrade` reversibles; tests de modelo |
| 40.2 | `canonical.py` + engine: conventions, derivations, base_ratios (Capa 1) | Unit tests de las 27 métricas base con sintéticos (DESIGN §5; eran 20 antes de la ampliación v2.1) |
| 40.3 | Engine: evolution (1.5) + forensic (2) + dividend (3) + stress (3.5) + synthesis (4) + version.py | Unit tests por métrica; golden test con fixture sintético completo |
| 40.4 | Adapter EDGAR + cache + concept_map + normalization + validation + restatements + IngestionJob + endpoints de fundamentales | Fixtures reales capturados; tests de normalización y restatement; smoke manual contra EDGAR documentado |
| 40.5 | Endpoints de análisis + AnalysisRun + goldens con empresas reales | Golden tests; 409/200 según estado de datos |
| 40.6 | Web Tab Análisis (buscador, ingesta con polling, informe completo) | Flujo end-to-end manual: ticker → ingesta → run → informe |
| 40.7 | Cartera backend: lots/sales/FIFO/allocations/dividends/corporate actions | Tests FIFO y corporate actions |
| 40.8 | Pricing: PriceAdapter + finnhub.py + price_quotes + refresh TTL + symbol search integrado en el buscador + `/portfolio/summary` completo (§5.1) | Tests con adapter mockeado (fixtures); summary con posición sin quote → excluida de totales con badge |
| 40.8b | Web Tab Cartera + summary + buscador broker-like | Flujo manual completo |
| 40.9 | Registro del módulo `enabled` + integración Dashboard (decisión de reconciliación con `accounts` — requiere input del usuario antes de implementar) | — |

**Puntos donde el implementador DEBE parar y preguntar al usuario**:
(a) resultados del cruzado EDGAR si el usuario no los ha aportado al
llegar a 40.4 — el `concept_map` definitivo depende de ellos; (b)
política de reconciliación con `accounts` en 40.9; (c) cualquier
partida cuyo mapeo XBRL resulte ambiguo en las empresas de prueba —
documentar la duda en el phase doc y decidir con el usuario, no
elegir en silencio.

---

## 10. Anti-objetivos (no implementar)

- Ejecución de órdenes, brokers, OAuth con brokers.
- **Precio en tiempo real y streaming** (regulado, de pago,
  innecesario). Las quotes son EOD/horarias vía §8.1 — eso SÍ está
  en scope (fase 40.8).
- Histórico de precios (charts de cotización): una fila viva por
  security. Si algún día se quieren gráficos de precio, es otra fase
  con otra tabla.
- Scraping de Google Finance o Yahoo Finance: descartado (sin API
  oficial, ToS, fragilidad).
- Valoración DCF/múltiplos.
- Scoring de financieras (bancos/aseguradoras).
- Ingesta 10-Q (el modelo lo prevé; no se implementa en 40.x).
- Colas externas (Celery/Redis): BackgroundTasks basta en local-first.
- Cualquier métrica o umbral que no esté en el DESIGN v2 §5.
