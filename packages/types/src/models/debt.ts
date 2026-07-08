/**
 * Tipos del módulo deuda (PHASE-22).
 */

export interface AmortizationRow {
  /** PHASE-24.1: id estable de la cuota persistida (null en cuentas
   * legacy sin cuotas materializadas todavía). */
  id?: string | null;
  month: number;
  due_date: string;
  payment: string;
  interest: string;
  principal: string;
  remaining_balance: string;
  /** PHASE-24.1: ISO timestamp; null = pendiente. */
  paid_at?: string | null;
  /** PHASE-24.1: tx del extracto que liquidó la cuota — informativo. */
  paid_transaction_id?: string | null;
}

/** PHASE-24.1: PATCH parcial de cuota — override puntual. */
export interface InstallmentUpdateRequest {
  payment?: string;
  due_date?: string;
}

/** PHASE-24.1: marcar cuota como pagada con timestamp + tx opcional. */
export interface InstallmentPayRequest {
  paid_at?: string;
  paid_transaction_id?: string;
}

/**
 * AUDIT-2026-07 (H-05): marca las cuotas que un pago de principal cubre.
 * Lo usa el asistente "Pagar cuota" para que el saldo dirigido por el cuadro
 * (PHASE-36) baje al pagar. `principal_amount` es un string decimal.
 */
export interface InstallmentBulkPayRequest {
  principal_amount: string;
  paid_at?: string;
  paid_transaction_id?: string;
}

export interface InstallmentBulkPayResponse {
  /** Cuántas cuotas se marcaron como pagadas. */
  marked_count: number;
  /** Σ del principal de las cuotas marcadas. */
  covered_principal: string;
  /** Principal pagado que no cubrió una cuota completa (0 si cuadró). */
  uncovered_principal: string;
  /** Saldo de la liability dirigido por el cuadro tras marcar. */
  schedule_outstanding: string | null;
}

export interface AmortizationSchedule {
  account_id: string;
  principal: string;
  /** TIN — usado para el cálculo. */
  apr: string;
  /** PHASE-24.2 — TAE (informativa). */
  tae?: string | null;
  term_months: number;
  start_date: string;
  monthly_payment: string;
  total_interest: string;
  /** Suma teórica de cuotas según el cuadro (Σ payment). */
  total_paid: string;
  /** PHASE-24.3 — Primera cuota especial sólo de intereses. */
  interest_only_first_payment?: string | null;
  /** PHASE-24.3 — Total contractualizado por el banco. */
  total_to_pay?: string | null;
  /** PHASE-24.3 — Cargos extra derivados: total_to_pay − total_paid − interest_only.
   * Null si no hay `total_to_pay`. */
  extra_charges?: string | null;
  rows: AmortizationRow[];
}

export type DtiStatus = 'healthy' | 'caution' | 'stressed' | 'unknown';

/** PHASE-37 — Porción de deuda viva por tipo de cuenta (donut de composición). */
export interface DebtTypeSlice {
  /** `loan` | `mortgage` | `credit_card`. */
  type: string;
  amount: string;
}

export interface DebtHealthKpis {
  total_liabilities: string;
  total_assets: string;
  net_worth: string;
  debt_to_assets_ratio: number | null;
  dti_ratio: number | null;
  dti_status: DtiStatus;
  monthly_debt_payment: string;
  monthly_income_avg: string;
  /**
   * PHASE-37 — Composición de la deuda viva por tipo desde el cuadro
   * (`schedule_outstanding`). STOCK (cuánto debes), no flujo de pagos.
   */
  debt_by_type: DebtTypeSlice[];
  /** PHASE-37 — Intereses pagados YTD desde el cuadro (MUX por pasivo). */
  interest_paid_ytd: string;
  /** PHASE-37 — Interés contractual total del cuadro (coste total del crédito). */
  interest_scheduled_total: string;
  /** PHASE-37 — Interés que queda por pagar (cuotas no pagadas). */
  interest_remaining: string;
  weighted_apr: number | null;
  time_to_payoff_months: number | null;
  reference_currency: string;
}

export type DebtHistoryPointKind = 'historical' | 'projected';

export interface DebtHistoryPoint {
  month: string;
  total_debt: string;
  principal_paid: string;
  interest_paid: string;
  kind: DebtHistoryPointKind;
}

export interface DebtHistoryResponse {
  items: DebtHistoryPoint[];
  reference_currency: string;
  months_historical: number;
  months_projected: number;
}

/* PHASE-30.2 — Capa 1 del módulo deuda: KPIs derivados del flujo de
 * categorías marcadas como deuda. Cubre /debt/category-summary. */

/**
 * PHASE-30.7 — Alineado con `PeriodKey` de `StitchPeriodToggle`
 * (dashboard + análisis) para que el selector de período sea
 * coherente en todo el producto.
 */
export type DebtTimeRange = 'month' | 'quarter' | 'year';

export type EffortStatus = 'healthy' | 'caution' | 'stressed' | 'unknown';

export type DebtTypeBucket = 'mortgage' | 'loan' | 'credit_card' | 'other';

export interface DebtTypeBreakdown {
  type: DebtTypeBucket;
  amount: string;
  /** Fracción en [0, 1]. */
  percent: number;
}

export interface MonthlyDebtPoint {
  /** `YYYY-MM`. */
  month: string;
  payments: string;
  interests: string;
  capital: string;
}

/**
 * PHASE-30.9 — Un día del mes en la vista diaria (sólo `range='month'`).
 * Modela la evolución del SALDO de deuda dentro del mes:
 * - `emitida`: cargos que suben la deuda (compras a plazos, aplazamientos).
 * - `amortizado`: pagos que la bajan (entradas a la cuenta-pasivo).
 * - `interest`: intereses pagados ese día (informativo, no mueve el saldo).
 * - `balance`: saldo de deuda al cierre del día; `null` si el usuario no
 *   tiene cuentas-pasivo (sin Capa 2 no hay línea de saldo).
 */
export interface DailyDebtPoint {
  /** Día del mes (1-31). */
  day: number;
  emitida: string;
  amortizado: string;
  interest: string;
  balance: string | null;
}

export interface RecurringQuotaRef {
  fixed_expense_id: string;
  merchant: string;
  amount: string;
  currency: string;
  category_id: string | null;
  category_name: string | null;
}

export interface DebtCategorySummary {
  reference_currency: string;
  range: DebtTimeRange;
  range_start: string;
  range_end: string;
  /**
   * PHASE-30.8 — `YYYY-MM` del primer/último mes con movimientos de
   * deuda (o `null`). Límites del navegador de período: las flechas se
   * detienen en estos extremos.
   */
  available_from: string | null;
  available_to: string | null;
  total_payments: string;
  interests_and_fees: string;
  capital_amortized: string;
  by_type: DebtTypeBreakdown[];
  monthly_series: MonthlyDebtPoint[];
  /**
   * PHASE-30.9 — Sólo para `range='month'`: un punto por día del mes con
   * la evolución del saldo de deuda. `null` en `quarter`/`year`.
   */
  daily_series: DailyDebtPoint[] | null;
  monthly_income_avg: string;
  /** PHASE-30.8 — Pago a deuda medio mensual del período (numerador
   * de la tasa de esfuerzo estricta). */
  monthly_debt_payment_avg: string;
  effort_ratio_strict: number | null;
  effort_ratio_strict_status: EffortStatus;
  effort_ratio_extended: number | null;
  effort_ratio_extended_status: EffortStatus;
  recurring_quotas: RecurringQuotaRef[];
}
