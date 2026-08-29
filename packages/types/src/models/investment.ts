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
/**
 * `not_applicable` llegó con el motor 1.4.0 (PHASE-44.17) y significa **la
 * pregunta que hace la métrica no se plantea aquí**, que no es «no se ha podido
 * responder». Puede traer banda: el muro de vencimientos de una empresa sin
 * deuda a doce meses es el mejor resultado posible, no un hueco. Un run anterior
 * nunca lo trae, así que la unión describe lo que puede haber en la tabla.
 */
export type MetricStatus = 'ok' | 'not_computable' | 'approximation' | 'not_applicable';
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
  /**
   * Clave opaca que se devuelve al servidor para materializar la fila
   * (PHASE-44.8 E2). El cliente NO manda plaza ni CIK: los mandaba —`'US'`, que
   * es un país— y eso duplicaba valores contra la restricción única
   * `(ticker, exchange)`. Lo que no se envía no se puede inventar.
   */
  listing_key: string;
  /**
   * `'catalog'` (ya en el catálogo), `'sec_index'` (índice de la SEC) o
   * `'eu_directory'` (directorio FIRDS UE/UK, PHASE-44.14).
   */
  source: string;
  cik: string | null;
  /**
   * Identidad registral de las filas del directorio (PHASE-44.14): no llevan
   * ticker (FIRDS no lo publica) y el ISIN es lo que las distingue en pantalla.
   */
  isin: string | null;
  /** Divisa registral de las filas del directorio. */
  currency: string | null;
  /** Etiqueta de la plaza para pintar (`Nasdaq`, no `NASDAQ`). */
  exchange_label: string;
  /** Por qué NO se puede analizar. `null` cuando sí se puede. */
  analysis_reason: string | null;
}

export interface SecurityAdoptRequest {
  listing_key: string;
  /**
   * Bypass manual de la resolución ISIN→símbolo, sólo para claves `ext:`
   * (PHASE-44.14): cuando el proveedor de precios no reconoce el ISIN, el
   * servidor responde 422 `ticker_required` y el formulario lo pide. La
   * identidad (plaza, nombre, divisa) sigue viniendo del directorio, y el
   * ticker se valida contra una cotización real antes de persistir nada.
   */
  ticker?: string;
}

/**
 * El detalle estructurado del 422 `ticker_required` del alta `ext:`.
 * `prefill` es la identidad registral, para pintarla junto al campo de ticker.
 */
export interface TickerRequiredDetail {
  code: 'ticker_required';
  message: string;
  prefill: { isin: string; mic: string; name: string; currency: string };
}

export interface SecuritySearchResponse {
  results: SecuritySearchHit[];
  external_search_available: boolean;
  /**
   * Si el índice de emisores de la SEC está cargado. Cero resultados significan
   * dos cosas distintas —«no hay coincidencias» y «el índice no está
   * disponible»— y la segunda no se puede pintar como la primera.
   */
  index_ready: boolean;
  /**
   * Aviso cuando el vacío mentiría: `NESN` no devuelve nada porque SIX no
   * reporta a FIRDS (frontera suiza), no porque Nestlé no exista.
   */
  notice: string | null;
  /**
   * Fecha del último seed del directorio UE/UK, o `null` si está vacío
   * (PHASE-44.14). Cero resultados europeos SIN sembrar significa «no se ha
   * mirado», no «no cotiza en Europa» — la pantalla debe distinguirlos.
   */
  directory_seeded_at: string | null;
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
  /**
   * Por qué la vara no aplica a este (sector × norma), en español (motor ≥
   * 1.6.0): «el EBITDA carece de sentido en banca», «sin inventario material en
   * este sector». Sin ella, un número gris se lee como «no se ha podido
   * calcular» y el diagnóstico se va a las cuentas de la empresa cuando lo que
   * pasa es que la métrica no describe ese negocio.
   */
  not_applicable_reason?: string | null;
  /**
   * De dónde salió este corte (motor ≥ 1.7.0): `'generic'` la vara del
   * catálogo · `'sector'` el perfil del sector · `'financial'` el perfil
   * financiero, que se fusiona encima cuando el VALOR es una entidad
   * financiera aunque esté clasificado en otro sector · `'table'` una fila
   * recalibrada a mano.
   *
   * **Ausente en los runs anteriores a 1.7.0**, y ausente no es `'generic'`:
   * allí la procedencia no se registraba, así que la pantalla la deriva
   * comparando con la calibración de hoy y declara que es una derivación.
   * Deliberadamente `string` y no una unión cerrada, como `analysis_status`:
   * el conjunto puede crecer y un valor que el frontend aún no conozca no debe
   * romper el tipado.
   */
  origin?: string | undefined;
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
  /**
   * PHASE-44.23 — qué mide y cómo se calcula, en una frase, para la «i» del
   * informe. Vive en el engine junto a la fórmula: una definición escrita en la
   * pantalla no la contrasta nadie.
   *
   * **Opcional**: un backend anterior al glosario no lo manda.
   */
  help?: string | undefined;
  /**
   * PHASE-44.24 — por qué le importa a quien vive de los dividendos de esta
   * empresa. **Opcional**: un backend anterior no lo manda, y su ausencia se
   * lee como «no hay porqué escrito», no como cadena vacía que pintar.
   */
  why?: string | undefined;
  /**
   * PHASE-44.24 — hacia dónde se lee y con qué matices (medias de dos
   * ejercicios, no aplica a financieras, primer año degradado). **Opcional**
   * por el mismo motivo.
   */
  reading?: string | undefined;
}

export interface MetricCatalogResponse {
  items: MetricDefinition[];
  engine_version: string;
}

/**
 * Una variable de un score forense, con su nombre legible (PHASE-44.24.A).
 *
 * Existe porque la tarjeta de desglose imprimía la CLAVE del motor: en pantalla
 * se leía `DSRI`, `TATA`, `P4_cfo_supera_beneficio`. Mismo defecto que las
 * señales en crudo que cerró PHASE-44.9, mismo arreglo: la etiqueta sale del
 * engine, junto a la fórmula.
 */
export interface ScoreComponentHelp {
  key: string;
  label: string;
  what: string;
}

/** La ficha de un score forense: qué mide, por qué importa y cómo se lee. */
export interface ScoreHelp {
  key: string;
  what: string;
  why: string;
  reading: string;
  /**
   * Vacío en los cuatro scores que no publican desglose por diseño (`accruals`,
   * `F5`, `F6`, `FZ`): son un ratio único. La lista vacía ES el dato.
   */
  components: ScoreComponentHelp[];
}

/**
 * La ficha de una bandera del motor (PHASE-44.24.A.2).
 *
 * `how_to_verify` es lo que la distingue: dice DÓNDE mirar en las cuentas para
 * confirmarla o descartarla. Sin él una bandera es un oráculo.
 */
export interface FlagHelp {
  key: string;
  label: string;
  what: string;
  why: string;
  reading: string;
  how_to_verify: string;
}

export interface HelpCatalogResponse {
  scores: ScoreHelp[];
  flags: FlagHelp[];
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
  /**
   * PHASE-44.23 — qué es la partida, en una frase, para la «i» del informe.
   *
   * **Opcional**: un backend anterior al glosario no lo manda. Su ausencia se
   * lee como «no hay definición», no como cadena vacía que pintar.
   */
  help?: string | undefined;
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
/**
 * Qué le pasó a una señal candidata (motor ≥ 1.5.0).
 *
 * - `scored` — puntuó en el semáforo.
 * - `clear` — se comprobó y no saltó. Es evidencia POSITIVA, no un hueco.
 * - `unchecked` — no se pudo comprobar. Esto sí es ausencia de evidencia.
 * - `informational` — no puntúa por diseño (banderas `info`, métricas sin banda
 *   absoluta).
 */
export type SignalOutcome = 'scored' | 'clear' | 'unchecked' | 'informational';

export interface QuestionSignal {
  key: string;
  label: string;
  kind: 'metric' | 'flag' | 'derived';
  band: MetricBand | null;
  value: string | null;
  status: MetricStatus | null;
  counted: boolean;
  reason: string | null;
  /**
   * AUSENTE en los runs anteriores al motor 1.5.0 — y ausente no es
   * `'unchecked'`: en aquellos runs la distinción no se registraba, así que
   * afirmar cualquiera de los cuatro sería inventarla.
   */
  outcome?: SignalOutcome;
}

export interface QuestionVerdict {
  key: string;
  question: string;
  verdict: MetricBand;
  red_signals: string[];
  amber_signals: string[];
  /**
   * AUSENTES en los runs anteriores a PHASE-44.9 (motor < 1.1.0) — no vacíos.
   *
   * Un `AnalysisRun` es JSONB persistido: lo que se guardó con el motor de
   * entonces se lee tal cual años después, así que el tipo describe la UNIÓN de
   * todas las versiones que puede haber en la tabla, no la que produce el motor
   * de hoy. Declararlos obligatorios costó un crash en producción con el único
   * valor del usuario analizado antes de 44.9 (MCD): `signals.length` sobre
   * `undefined`. El `?` es lo que obliga a `tsc` a enumerar los consumidores.
   *
   * Y ausente **no es cero**: la pregunta sí evaluó señales, el motor no las
   * registraba. Pintar `0` sería inventarse un dato — la misma convención
   * «hueco ≠ 0» que el engine aplica desde PHASE-44.2 §4.5.
   */
  signals?: QuestionSignal[];
  evaluated_count?: number;
  unavailable_count?: number;
  /**
   * Los dos que PARTEN `unavailable_count` (motor ≥ 1.5.0), que metía en un
   * solo cubo cuatro cosas: no se pudo calcular, la bandera no saltó —buena
   * noticia—, es informativa por diseño, y no aplica. En McDonald's la pregunta
   * sobre la contabilidad decía «7 no disponibles» sobre 2 huecos reales y 5
   * banderas comprobadas y limpias: la pantalla subestimaba la evidencia
   * mientras el veredicto verde la sobreestimaba.
   *
   * Opcionales por la misma razón que los de arriba: la tabla guarda runs de
   * todas las versiones, y un `0` donde no hay dato es un dato inventado.
   */
  clear_count?: number;
  unchecked_count?: number;
  /**
   * Los PORTANTES de la pregunta y si todos se pudieron evaluar (motor ≥ 1.6.0).
   *
   * No todas las señales pesan igual: «¿la contabilidad es de fiar?» se sostiene
   * en el M-Score y en los accruals, no en el peso de los extraordinarios. Antes
   * la guarda era todo-o-nada (`evaluated_count === 0`) y McDonald's salía verde
   * confiado con 3 señales de 10, con las dos que responden la pregunta muertas.
   *
   * `audited === false` es el CUARTO estado de una pregunta: gris, con la lista
   * de lo que falta. Ausente (`undefined`) en runs anteriores y eso NO es
   * `false`: en aquellos runs la distinción no se registraba.
   */
  load_bearing?: string[];
  audited?: boolean;
  unaudited_reasons?: string[];
  /**
   * Avisos sobre el ALCANCE de un veredicto que sí se sostiene: en una
   * financiera, un verde de contabilidad es verde con cobertura forense
   * limitada. Decirlo es la diferencia entre un verde honesto y uno que promete
   * de más.
   */
  notes?: string[];
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
  /**
   * Los tres factores del desdoble de 5 llegaron en PHASE-44.10 (motor < 1.2.0
   * no los tiene). Opcionales por el mismo motivo que `QuestionVerdict.signals`:
   * la tabla guarda runs de todas las versiones.
   */
  operating_margin?: MetricResult;
  tax_effect?: MetricResult;
  financial_cost?: MetricResult;
  /**
   * `(producto de los factores) − ROE`. Debe ser 0.
   *
   * `null` es **no verificable** (falta algún factor), que NO es lo mismo que
   * verificado: un cuadre que no se ha podido comprobar nunca se presenta como
   * superado.
   */
  check_three?: string | null;
  check_five?: string | null;
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
  /**
   * Ausente en un run de motor 1.0.0 (la fixture real de MCD trae
   * `evolution: {}`). Opcional por la regla de PHASE-44.16: un `AnalysisRun`
   * es JSONB de todas las versiones, y declararlo obligatorio apaga al
   * compilador justo donde hace falta — la pantalla pintaba una tabla con
   * cabecera de años y cero filas sin poder avisar.
   */
  metrics: MetricResult[];
  horizontal?: HorizontalSeries[];
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
  /**
   * PHASE-44.24.C — distancia al corte, orden por severidad y procedencia.
   * **Opcional**: un backend anterior no la manda, y su ausencia se lee como
   * «esta versión del servidor no la calcula», no como capa vacía.
   */
  report?: ReportLayer | undefined;
}

/**
 * A qué distancia está una señal del corte que decide su banda (PHASE-44.24.C).
 *
 * El TEXTO no viene hecho: «a 3 pp del verde» para un margen y «2,1× dentro del
 * rojo» para una cobertura son la misma información dicha por unidad, y quien
 * sabe formatear por unidad es `@crisol/ui` — que además lo hace igual en las
 * dos apps.
 */
export interface SignalDistance {
  cut: string | null;
  absolute: string | null;
  /**
   * `null` con el corte en cero y en las métricas de puntuación, donde no
   * significa nada: los cortes del X-Score están en −1,04 y −0,25, así que la
   * misma distancia da relativas de 0,2 y 0,8 sin que ninguna informe.
   */
  relative: string | null;
  side: 'inside' | 'outside';
  /** Con cortes iguales NUNCA es `caution`: esa región es vacía. */
  next_band: 'caution' | 'stressed';
  /** Por qué no hay corte hacia donde medir (S7 por debajo de su banda). */
  missing_reason?: string | null;
}

/**
 * De dónde salió la vara con la que se midió una señal.
 *
 * `not_recorded` es «el run no registró el corte de ESTA métrica», que no es la
 * genérica: un run de motor 1.3.0 tiene `thresholds_used` y no tiene S7 ni S8.
 * `earlier_calibration` sólo aparece en runs anteriores al motor 1.7.0, donde
 * la procedencia se deriva en vez de leerse.
 */
export type ThresholdOrigin =
  | 'generic'
  | 'sector'
  | 'financial'
  | 'table'
  | 'earlier_calibration'
  | 'uncalibrated'
  | 'not_applicable'
  | 'not_recorded';

export interface ReportSignal {
  key: string;
  /** Para imprimir la marca de aproximación junto al valor (regla 3). */
  status?: MetricStatus | null;
  /** 0 = la peor. Resuelto en el servidor: las dos apps no pueden discrepar. */
  severity_rank: number;
  distance?: SignalDistance | null;
  threshold_origin: ThresholdOrigin;
}

export interface ReportQuestion {
  key: string;
  /**
   * El estado en que se puede leer el veredicto. Sólo `evaluated` permite
   * nombrar el color; los otros tres son el motivo por el que no.
   */
  evidence?: 'evaluated' | 'no-evidence' | 'not-recorded' | 'not-audited';
  /** Si el run distingue «comprobada y limpia» de «no se pudo comprobar». */
  outcomes_recorded?: boolean;
  /** La frase determinista de esta pregunta (PHASE-44.24.B). */
  sentence?: string;
  signals: ReportSignal[];
}

export interface NextCheck {
  key: string;
  text: string;
}

/**
 * Qué perfil de umbrales gobierna a este valor HOY.
 *
 * Lo emite el servidor entero: componerlo en la pantalla con `security.sector`
 * es falso para toda entidad financiera clasificada en otro sector, porque el
 * perfil financiero se fusiona por encima del sectorial.
 */
export interface ThresholdProfile {
  effective: string;
  sector: SectorInternal;
  is_financial: boolean;
  is_reit: boolean;
}

/**
 * La capa de LECTURA de un run (PHASE-44.24.C): no se persiste, se calcula al
 * servirlo. Así un run de un motor anterior la recibe hoy sin reejecutar nada.
 *
 * **Opcional**: un backend anterior no la manda.
 */
export interface ReportLayer {
  threshold_profile: ThresholdProfile;
  questions: ReportQuestion[];
  /**
   * La versión de los TEXTOS, distinta de la del motor: reescribir una frase no
   * cambia ningún número, así que no marca como caducado ningún análisis.
   */
  narrative_version?: string;
  /** Perfil de seguridad y dividendo, en una frase. */
  headline?: string;
  /** Hasta tres cosas que mirar, las peores primero. */
  next_checks?: NextCheck[];
}

export interface AnalysisRunSummary {
  id: string;
  run_date: string;
  engine_version: string;
  /**
   * Para etiquetar «comparable» en el selector SIN pedir los runs enteros.
   *
   * Opcional porque un backend anterior a PHASE-44.24.F no lo manda, y
   * `campo !== undefined` sobre una clave ausente es cómo se pinta una marca
   * en todas las filas.
   */
  thresholds_version?: string;
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

// ── Comparador de runs (PHASE-44.24.F) ────────────────────────────────

export interface ScoreChange {
  key: string;
  before: string | null;
  after: string | null;
  band_before: MetricBand | null;
  band_after: MetricBand | null;
}

export interface BandChange {
  key: string;
  band_before: MetricBand | null;
  band_after: MetricBand | null;
  value_before: string | null;
  value_after: string | null;
}

export interface FlagChange {
  key: string;
  label: string | null;
  severity: string | null;
  /** `true` si la bandera ha APARECIDO; `false` si se ha apagado. */
  appeared: boolean;
}

export interface QuestionChange {
  key: string;
  verdict_before: MetricBand | null;
  verdict_after: MetricBand | null;
  /** El estado de evidencia, no el color: se puede perder respaldo sin
   *  cambiar de banda, y eso también es una noticia. */
  evidence_before: string;
  evidence_after: string;
}

export interface RestatementNote {
  fiscal_year: number;
  filing_a: string;
  filing_b: string;
  item_count: number;
}

/**
 * Qué ha cambiado entre dos análisis de la misma empresa.
 *
 * `comparable === false` significa que cambió el MÉTODO (motor o calibración):
 * entonces las listas de cambios de empresa vienen VACÍAS por construcción,
 * porque un cambio de banda podría ser el corte y no el negocio.
 */
export interface RunDiff {
  comparable: boolean;
  base_id: string;
  target_id: string;
  base_date: string | null;
  target_date: string | null;
  method_changes: string[];
  years_added: number[];
  years_removed: number[];
  safety_before: SafetyLabel | null;
  safety_after: SafetyLabel | null;
  dividend_before: DividendVerdict | null;
  dividend_after: DividendVerdict | null;
  questions: QuestionChange[];
  scores: ScoreChange[];
  bands: BandChange[];
  flags: FlagChange[];
  restatements: RestatementNote[];
  caveat: string | null;
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
