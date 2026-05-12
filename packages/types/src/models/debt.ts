/**
 * Tipos del módulo deuda (PHASE-22).
 */

export interface AmortizationRow {
  month: number;
  due_date: string;
  payment: string;
  interest: string;
  principal: string;
  remaining_balance: string;
}

export interface AmortizationSchedule {
  account_id: string;
  principal: string;
  apr: string;
  term_months: number;
  start_date: string;
  monthly_payment: string;
  total_interest: string;
  total_paid: string;
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
