/**
 * Tipos del módulo Inversión (PHASE-44.7).
 *
 * Los importes y ratios llegan del backend como STRING decimal (nunca number),
 * igual que el resto de la API — se formatean en render con `formatAmount`. Los
 * campos "enum-like" son uniones de string literal.
 */

export type SectorInternal =
  | 'technology'
  | 'healthcare'
  | 'financials'
  | 'consumer_staples'
  | 'consumer_discretionary'
  | 'industrials'
  | 'energy'
  | 'materials'
  | 'utilities'
  | 'real_estate'
  | 'communication'
  | 'unknown';

export type AccountingStd = 'GAAP' | 'IFRS' | 'PGC';
export type SecurityType = 'STOCK' | 'ADR' | 'ETF';
export type JobStatus = 'pending' | 'running' | 'done' | 'failed';
export type CorpActionType = 'split' | 'spinoff' | 'stock_dividend' | 'return_of_capital';

export type MetricBand = 'healthy' | 'caution' | 'stressed';
export type MetricStatus = 'ok' | 'not_computable' | 'approximation';
export type Provenance = 'sourced' | 'derived' | 'imputed_zero' | 'estimated';
export type FlagSeverity = 'info' | 'amber' | 'red';
export type DividendVerdict = 'healthy' | 'caution' | 'stressed' | 'not_applicable';
export type SafetyLabel = 'conservative' | 'watch' | 'avoid';

// ── Catálogo ──────────────────────────────────────────────────────────

export interface Security {
  id: string;
  ticker: string;
  exchange: string;
  name: string;
  cik: string | null;
  isin: string | null;
  sector: SectorInternal;
  accounting_std: AccountingStd;
  currency: string;
  security_type: SecurityType;
  is_financial: boolean;
  is_reit: boolean;
  /**
   * Evidencia de si el motor puede correr sobre este valor (PHASE-44.8):
   * `'ok' | 'no_annual' | 'non_gaap' | 'not_supported'`, o `null` si no se ha
   * comprobado. Es deliberadamente `string` y no una unión cerrada: el conjunto
   * crecerá, y un valor que el frontend aún no conozca no debe romper el tipado.
   * Para decidir, usa `analysis_available`; para explicar, `analysis_reason`.
   */
  analysis_status: string | null;
  analysis_available: boolean;
  /**
   * Por qué NO se puede analizar, cuando `analysis_available` es `false`.
   * Existe para poder decirlo en la fila antes del clic en vez de dejar que la
   * petición falle después (PHASE-44.8 E1).
   */
  analysis_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface SecuritySearchHit {
  id: string | null;
  ticker: string;
  exchange: string;
  name: string;
  in_catalog: boolean;
  analysis_available: boolean;
}

export interface SecuritySearchResponse {
  results: SecuritySearchHit[];
  external_search_available: boolean;
}

// ── Fundamentales ─────────────────────────────────────────────────────

export interface IngestionJob {
  id: string;
  security_id: string;
  status: JobStatus;
  params: Record<string, unknown>;
  progress: Record<string, unknown>;
  error: string | null;
  created_at: string;
  finished_at: string | null;
}

/** Una partida canónica: string decimal o null (hueco). */
type Money = string | null;

export interface FinancialStatement {
  id: string;
  security_id: string;
  fiscal_year: number;
  fiscal_year_end: string;
  period_type: 'ANNUAL' | 'QUARTERLY';
  filing_accession: string;
  filing_date: string;
  is_latest_view: boolean;
  source: 'EDGAR_XBRL' | 'MANUAL';
  accounting_std: AccountingStd;
  currency: string;
  // 49 partidas canónicas (balance + resultados + flujo de caja).
  cash: Money;
  current_financial_assets: Money;
  receivables: Money;
  inventory: Money;
  current_assets: Money;
  ppe_net: Money;
  goodwill: Money;
  intangibles: Money;
  deferred_tax_assets: Money;
  total_assets: Money;
  short_term_debt: Money;
  ltd_current_portion: Money;
  accounts_payable: Money;
  lease_liabilities_current: Money;
  current_liabilities: Money;
  long_term_debt: Money;
  lease_liabilities_noncurrent: Money;
  deferred_tax_liabilities: Money;
  total_liabilities: Money;
  share_premium: Money;
  retained_earnings: Money;
  treasury_stock: Money;
  equity: Money;
  revenue: Money;
  cogs: Money;
  sga_expense: Money;
  rd_expense: Money;
  depreciation_amortization: Money;
  impairments: Money;
  gains_on_sale_of_business: Money;
  ebit: Money;
  interest_expense: Money;
  pretax_income: Money;
  taxes: Money;
  net_income: Money;
  shares_basic: Money;
  shares_diluted: Money;
  shares_outstanding_eop: Money;
  sbc_expense: Money;
  cfo: Money;
  wc_change_inventory: Money;
  capex: Money;
  acquisitions: Money;
  divestitures: Money;
  dividends_paid: Money;
  buybacks: Money;
  share_issuance: Money;
  debt_change: Money;
  taxes_paid: Money;
  raw_source_ref: Record<string, unknown>;
  created_at: string;
}

export interface StatementListResponse {
  items: FinancialStatement[];
}

export interface RestatementFlag {
  id: string;
  security_id: string;
  fiscal_year: number;
  filing_a: string;
  filing_b: string;
  divergences: Record<string, string>[];
  detected_at: string;
}

export interface RestatementListResponse {
  items: RestatementFlag[];
}

// ── Análisis (engine) ─────────────────────────────────────────────────

export interface MetricResult {
  key: string;
  fiscal_year: number;
  value: string | null;
  status: MetricStatus;
  provenance: Provenance;
  reason: string | null;
  band: MetricBand | null;
}

export interface EngineFlag {
  key: string;
  severity: FlagSeverity;
  message: string;
  evidence: Record<string, unknown>;
}

export interface QuestionVerdict {
  key: string;
  question: string;
  verdict: MetricBand;
  red_signals: string[];
  amber_signals: string[];
}

export interface SafetyProfile {
  label: SafetyLabel;
  blocking_reasons: string[];
}

export interface Confidence {
  value: string;
  completeness_core: string;
  staleness_factor: string;
  imputed_core_count: number;
  latest_fiscal_year_end: string | null;
  days_stale: number | null;
}

export interface VerdictBlock {
  questions: QuestionVerdict[];
  safety_profile: SafetyProfile;
  dividend_verdict: DividendVerdict;
  stress: Record<string, unknown>;
}

/** Colección de métricas de una capa (forensic / base / dividend / evolution). */
export interface MetricCollection {
  metrics: MetricResult[];
  flags?: EngineFlag[];
  [key: string]: unknown;
}

export interface AnalysisRun {
  id: string;
  security_id: string;
  run_date: string;
  engine_version: string;
  thresholds_version: string;
  years_covered: number[];
  m_score: string | null;
  z_score: string | null;
  z_variant: string | null;
  f_score: number | null;
  accruals_ratio: string | null;
  fcf_payout: string | null;
  fcf_coverage: string | null;
  dividend_verdict: DividendVerdict | null;
  confidence: string;
  scores_detail: { forensic: MetricCollection; base_ratios: MetricCollection };
  dividend_analysis: MetricCollection;
  evolution: MetricCollection;
  flags: EngineFlag[];
  verdict: VerdictBlock;
  data_completeness: Confidence;
}

export interface AnalysisRunSummary {
  id: string;
  run_date: string;
  engine_version: string;
  years_covered: number[];
  m_score: string | null;
  z_score: string | null;
  f_score: number | null;
  dividend_verdict: DividendVerdict | null;
  confidence: string;
}

export interface AnalysisRunListResponse {
  items: AnalysisRunSummary[];
}

// ── Cartera ───────────────────────────────────────────────────────────

export interface Lot {
  id: string;
  security_id: string;
  account_id: string | null;
  trade_date: string;
  quantity: string;
  price: string;
  fx_rate_at_trade: string;
  fees: string;
  created_at: string;
}

export interface Sale {
  id: string;
  security_id: string;
  trade_date: string;
  quantity: string;
  price: string;
  fx_rate_at_trade: string;
  fees: string;
  created_at: string;
}

export interface Dividend {
  id: string;
  security_id: string;
  ex_date: string | null;
  pay_date: string;
  gross_amount: string;
  withholding_tax: string;
  net_amount: string;
  currency: string;
  fx_rate: string;
  created_at: string;
}

export interface CorporateAction {
  id: string;
  security_id: string;
  action_type: CorpActionType;
  action_date: string;
  ratio: string | null;
  notes: string | null;
  applied_at: string | null;
  created_at: string;
}

export interface Position {
  security_id: string;
  ticker: string;
  name: string;
  currency: string;
  quantity: string;
  avg_cost: string | null;
  cost_basis: string;
  realized_pnl: string;
  dividends_gross: string;
  dividends_net: string;
}

export interface PositionSummary extends Position {
  has_quote: boolean;
  last_price: string | null;
  prev_close: string | null;
  quote_as_of: string | null;
  quote_stale: boolean;
  market_value: string | null;
  unrealized_pnl: string | null;
  unrealized_pnl_pct: string | null;
  price_effect: string | null;
  fx_effect: string | null;
  daily_change: string | null;
  total_return: string | null;
  yield_on_cost: string | null;
  weight_pct: string | null;
}

export interface PortfolioSummary {
  pricing_enabled: boolean;
  base_note: string;
  total_cost_basis: string;
  total_market_value: string;
  total_unrealized_pnl: string;
  total_realized_pnl: string;
  total_dividends_net: string;
  daily_pnl: string;
  quoted_count: number;
  unquoted_count: number;
  positions: PositionSummary[];
}
