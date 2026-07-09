// PHASE-37.3 — Gasto estructural vs puntual + tasa de ahorro dual.

/** Referencia ligera a una transacción (listas del análisis). */
export interface AnalyticsTxRef {
  id: string;
  description: string | null;
  amount: string;
  converted_amount: string | null;
  currency: string;
  occurred_at: string;
  category_id: string | null;
  category_name: string | null;
}

/** Total agregado por categoría (con color/icon para chips). */
export interface AnalyticsCategoryAmount {
  category_id: string | null;
  category_name: string | null;
  color: string | null;
  icon: string | null;
  total: string;
}

export interface ExpenseStructureResponse {
  reference_currency: string;
  income_total: string;
  /** Gasto recurrente (fixed_expenses, deuda, categorías estables). */
  structural_total: string;
  /** Gasto puntual (one-offs: impuestos, dentista, reformas…). */
  exceptional_total: string;
  /** Media mensual del gasto estructural en la ventana — base del runway. */
  structural_monthly_avg: string;
  /** (ingresos − gasto total) / ingresos. `null` si ingresos ≤ 0. */
  savings_rate_gross: number | null;
  /** (ingresos − gasto estructural) / ingresos. `null` si ingresos ≤ 0. */
  savings_rate_structural: number | null;
  top_exceptional: AnalyticsTxRef[];
  exceptional_by_category: AnalyticsCategoryAmount[];
}

// PHASE-37.4 — Proyección de fin de mes + runway.

export interface CommittedItem {
  name: string;
  amount: string;
  /** Día de cargo estimado (`YYYY-MM-DD`). */
  expected_date: string;
  /** `true` si ya venció este mes y sigue sin cargarse/pagarse. */
  overdue: boolean;
  kind: 'fixed' | 'installment';
}

export interface MonthOutlookResponse {
  reference_currency: string;
  /** Σ de lo comprometido aún este mes (gastos fijos + cuotas). */
  committed_remaining: string;
  committed_items: CommittedItem[];
  days_remaining: number;
  /** Σ saldo de cuentas líquidas (bank/savings/cash) no archivadas. */
  liquid_balance: string;
  /** `liquid_balance / gasto estructural mensual`; `null` sin base o sin colchón. */
  runway_months: number | null;
}
