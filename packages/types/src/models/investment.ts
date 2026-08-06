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

/** Cómo se lee el valor de una métrica. Lo declara el catálogo del engine. */
export type MetricUnit =
  | 'percent'
  | 'times'
  | 'days'
  | 'years'
  | 'pp'
  | 'score'
  | 'count'
  | 'currency_per_share';

export type ThresholdDirection = 'lower_better' | 'higher_better' | 'band';

/** Los cuatro cortes de una banda. Los mismos campos en el catálogo y en
 *  `AnalysisRun.thresholds_used`. */
export interface ThresholdSpec {
  metric_key: string;
  direction: ThresholdDirection;
  low_alarm: string | null;
  low_ok: string | null;
  high_ok: string | null;
  high_alarm: string | null;
  model_variant: string | null;
  applies: boolean;
}

/**
 * Una métrica del catálogo del engine (PHASE-44.9).
 *
 * Antes de que este catálogo viajara por API, la web escribía las etiquetas a
 * mano y tres acabaron mintiendo sobre el número que enseñaban. Ahora la
 * etiqueta tiene una sola fuente.
 */
export interface MetricDefinition {
  key: string;
  label: string;
  family: string;
  unit: MetricUnit;
  /** `null` = **sin banda absoluta**. NO significa «sana». */
  direction: ThresholdDirection | null;
  low_alarm: string | null;
  low_ok: string | null;
  high_ok: string | null;
  high_alarm: string | null;
  model_variant: string | null;
  note: string;
}

export interface MetricCatalogResponse {
  items: MetricDefinition[];
  engine_version: string;
}

// ── Catálogo de partidas canónicas ────────────────────────────────────

export type StatementKind = 'balance' | 'income' | 'cashflow';

export type ItemGroup =
  | 'assets_current'
  | 'assets_noncurrent'
  | 'liabilities_current'
  | 'liabilities_noncurrent'
  | 'equity'
  | 'income_gross'
  | 'income_operating'
  | 'income_financial'
  | 'income_tax'
  | 'income_result'
  | 'income_shares'
  | 'cashflow_operating'
  | 'cashflow_investing'
  | 'cashflow_financing';

/** Una de las 49 partidas, con su nombre en español y su bloque. */
export interface CanonicalItemDefinition {
  key: string;
  label: string;
  statement: StatementKind;
  group: ItemGroup;
  note: string;
}

export interface CanonicalItemCatalogResponse {
  items: CanonicalItemDefinition[];
}

/**
 * Una señal candidata de una pregunta, haya puntuado o no (PHASE-44.9).
 *
 * `counted: false` **no** es «está bien»: es «no cuenta», y entonces `reason`
 * explica por qué. Si todas las señales de una pregunta llegan sin contar, el
 * verde es por ausencia de prueba y hay que pintarlo gris.
 */
export interface QuestionSignal {
  key: string;
  label: string;
  kind: 'metric' | 'flag' | 'derived';
  band: MetricBand | null;
  value: string | null;
  status: MetricStatus | null;
  counted: boolean;
  reason: string | null;
}

export interface QuestionVerdict {
  key: string;
  question: string;
  verdict: MetricBand;
  red_signals: string[];
  amber_signals: string[];
  /** Vacío en los runs anteriores a PHASE-44.9. */
  signals: QuestionSignal[];
  evaluated_count: number;
  unavailable_count: number;
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

/** Un escenario de stress con su frase ya redactada por el motor. */
export interface StressScenario {
  key: string;
  parameter: string;
  coverage_before: string | null;
  coverage_after: string | null;
  sentence: string;
  /** Siempre «escenario hipotético». El motor lo fija para que nadie lo lea
   *  como una previsión. */
  label: string;
}

export interface StressBlock {
  scenarios: StressScenario[];
  /** `null` → ST1 no se calculó y `not_computable_reason` dice por qué. */
  contribution_margin: string | null;
  breakeven_fcf_drop: string | null;
  not_computable_reason: string | null;
}

export interface VerdictBlock {
  questions: QuestionVerdict[];
  safety_profile: SafetyProfile;
  dividend_verdict: DividendVerdict;
  stress: StressBlock;
}

/**
 * Las dos descomposiciones del ROE, por ejercicio.
 *
 * - 3 factores: `margen neto × rotación × apalancamiento`.
 * - 5 factores: `margen operativo × efecto fiscal × coste financiero ×
 *   rotación × apalancamiento` — desdobla el margen neto en de dónde sale.
 */
export interface DuPontDecomposition {
  fiscal_year: number;
  net_margin: MetricResult;
  asset_turnover: MetricResult;
  equity_multiplier: MetricResult;
  operating_margin: MetricResult;
  tax_effect: MetricResult;
  financial_cost: MetricResult;
  /**
   * `(producto de los factores) − ROE`. Debe ser 0.
   *
   * `null` es **no verificable** (falta algún factor), que NO es lo mismo que
   * verificado: un cuadre que no se ha podido comprobar nunca se presenta como
   * superado.
   */
  check_three: string | null;
  check_five: string | null;
}

export interface BaseRatiosBlock {
  metrics: MetricResult[];
  flags: EngineFlag[];
  dupont: DuPontDecomposition[];
}

/**
 * Desglose de un score forense. Sólo 4 de las 8 claves lo emiten, y de forma
 * condicional: `accruals`, `F5`, `F6` y `FZ` **nunca** lo traen por diseño.
 */
export interface ScoreBreakdown {
  key: string;
  fiscal_year: number;
  /** M-Score: sus 8 variables. Z'': X1-X4. Vacío en los de sólo checks. */
  components: Record<string, string>;
  /** F-Score: sus 9 tests. C-Score: sus 6. Vacío en los de componentes. */
  checks: Record<string, boolean>;
}

export interface ForensicBlock {
  metrics: MetricResult[];
  breakdowns: ScoreBreakdown[];
  flags: EngineFlag[];
}

export interface HorizontalPoint {
  fiscal_year: number;
  value: string | null;
  yoy: string | null;
}

/** Una de las 7 magnitudes de la evolutiva, con su etiqueta ya en español. */
export interface HorizontalSeries {
  key: string;
  label: string;
  points: HorizontalPoint[];
  cagr: string | null;
  /** Por qué no hay CAGR (signo cambiado, serie corta…). */
  cagr_reason: string | null;
}

/** Common-size: peso de una partida sobre su base, por ejercicio. */
export interface VerticalPoint {
  fiscal_year: number;
  item: string;
  base: string;
  weight: string | null;
}

export interface EvolutionBlock {
  metrics: MetricResult[];
  horizontal: HorizontalSeries[];
  vertical: VerticalPoint[];
  flags: EngineFlag[];
}

export interface DpsPoint {
  fiscal_year: number;
  dps: string | null;
}

export interface DividendTrajectory {
  /** Años seguidos sin recorte. Es una **cota inferior**: la serie es la
   *  ingerida, no el histórico completo de la empresa. */
  streak_no_cut: number;
  momentum_slowdown: boolean;
}

export interface DividendBlock {
  metrics: MetricResult[];
  dps_series: DpsPoint[];
  trajectory: DividendTrajectory;
  flags: EngineFlag[];
}

export interface AnalysisRun {
  id: string;
  security_id: string;
  run_date: string;
  engine_version: string;
  thresholds_version: string;
  /**
   * Los cortes EFECTIVOS de este run, `metric_key → spec` (PHASE-44.9). `{}` en
   * los runs anteriores: su calibración no es recuperable, porque el seed muta
   * las filas in situ y `thresholds_version` es un hash irreversible.
   */
  thresholds_used: Record<string, ThresholdSpec>;
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
  scores_detail: { forensic: ForensicBlock; base_ratios: BaseRatiosBlock };
  dividend_analysis: DividendBlock;
  evolution: EvolutionBlock;
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
  /**
   * Por qué la posición no entra en los totales — `null` si sí entra. "Sin
   * cotización" a secas obliga a adivinar si el problema es el proveedor, la
   * plaza o la falta de tipo de cambio.
   */
  exclusion_reason: string | null;
  last_price: string | null;
  prev_close: string | null;
  quote_as_of: string | null;
  quote_stale: boolean;
  /** Divisa que declaró el proveedor de precios, ya normalizada a ISO-4217. */
  quote_currency: string | null;
  /**
   * La divisa del proveedor no coincide con la del catálogo (PHASE-44.11 D4).
   * La posición se valora con la del proveedor —es quien emitió el precio— pero
   * la discrepancia se muestra: significa que el catálogo afirma una plaza o
   * divisa que el mercado contradice.
   */
  currency_mismatch: boolean;
  market_value: string | null;
  /** Valor de mercado en la divisa base de la cartera. `null` si falta la tasa. */
  market_value_base: string | null;
  /**
   * Coste en base al tipo de la FECHA DE COMPRA, no al de hoy: reexpresarlo a
   * tipo de hoy escondería el efecto divisa que la descomposición aísla.
   */
  cost_basis_base: string;
  unrealized_pnl_base: string | null;
  fx_rate: string | null;
  /**
   * Fecha EFECTIVA del tipo aplicado — no siempre es hoy (un lunes se usa el
   * del viernes). Un valor con precio de hoy y tasa de hace días debe decirlo.
   */
  fx_as_of: string | null;
  unrealized_pnl: string | null;
  unrealized_pnl_pct: string | null;
  price_effect: string | null;
  fx_effect: string | null;
  daily_change: string | null;
  total_return: string | null;
  yield_on_cost: string | null;
  weight_pct: string | null;
}

/** Exposición de la cartera a una divisa, valorada en la divisa base. */
export interface CurrencyExposure {
  currency: string;
  market_value_base: string;
  weight_pct: string;
}

export interface PortfolioSummary {
  pricing_enabled: boolean;
  /** Divisa en la que se agregan los totales (`total_*_base`). */
  base_currency: string;
  base_note: string;
  /** Suma en divisa NATIVA. Sólo interpretable si la cartera es monodivisa. */
  total_cost_basis: string;
  total_cost_basis_base: string;
  total_market_value: string;
  total_market_value_base: string;
  /** Suma en divisa NATIVA — usa `total_unrealized_pnl_base` para agregar. */
  total_unrealized_pnl: string;
  total_unrealized_pnl_base: string;
  total_realized_pnl: string;
  total_dividends_net: string;
  daily_pnl: string;
  quoted_count: number;
  unquoted_count: number;
  currency_exposure: CurrencyExposure[];
  positions: PositionSummary[];
}

// ── Valoración por múltiplos (PHASE-44.12) ────────────────────────────

/** Un múltiplo. `value` es `null` si y sólo si no se puede calcular. */
export interface ValuationMetric {
  key: string;
  value: string | null;
  status: string;
  /** Por qué no se puede calcular, en español y para el usuario. */
  reason: string | null;
}

/**
 * Los múltiplos de un valor contra su cotización.
 *
 * NO sale del `AnalysisRun` y no se persiste: se calcula al vuelo cruzando el
 * último ejercicio cerrado con el precio del momento. Un análisis forense es
 * reproducible porque no depende del precio; esto sí, y por eso vive aparte y
 * la UI lo separa del veredicto.
 */
export interface Valuation {
  available: boolean;
  /** Por qué no hay múltiplos. `null` cuando sí los hay. */
  reason: string | null;
  /** El precio lo puso el usuario, no el proveedor. */
  price_is_override: boolean;
  metrics: ValuationMetric[];
  fiscal_year: number | null;
  fiscal_year_end: string | null;
  statement_currency: string | null;
  market_cap: string | null;
  enterprise_value: string | null;
  quote_as_of: string | null;
  quote_stale: boolean;
  /**
   * Estado del proveedor de cotizaciones en ESTA consulta:
   * - `live` — se le pidió y respondió.
   * - `cached` — no se le pidió (la cotización guardada seguía fresca), así que
   *   de su estado no se sabe nada. No es lo mismo que «está bien».
   * - `unreachable` — se le pidió y falló; se sirve el último precio registrado.
   */
  provider_status: 'live' | 'cached' | 'unreachable';
  fx_rate: string | null;
  fx_as_of: string | null;
  /**
   * Distancia entre el precio y las cuentas con que se compara. La mitad del
   * «doble staleness»: un PER con precio de hoy sobre un beneficio de hace
   * catorce meses no es falso, pero tiene que decirlo.
   */
  days_since_fiscal_year_end: number | null;
  /** `null` | `aging` (≥9 meses) | `stale` (≥18 meses). */
  staleness: string | null;
  notes: string[];
}
