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

export interface DebtHealthKpis {
  total_liabilities: string;
  total_assets: string;
  net_worth: string;
  debt_to_assets_ratio: number | null;
  dti_ratio: number | null;
  dti_status: DtiStatus;
  monthly_debt_payment: string;
  monthly_income_avg: string;
  interest_paid_ytd: string;
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
