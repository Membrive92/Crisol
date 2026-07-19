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
  /**
   * PHASE-43.1 — Ventana de recurrencia (meses naturales completos hasta
   * `min(date_to, hoy)`). `YYYY-MM-DD`.
   */
  window_start: string;
  window_end: string;
  /** Meses de la ventana con algún gasto registrado. */
  window_months_with_data: number;
  /**
   * PHASE-43.1 — `false` si `window_months_with_data < 4`: la regla 3 no
   * puede clasificar y sólo actúan gastos fijos + deuda. La UI debe avisarlo
   * en vez de mostrar una tasa estructural engañosa.
   */
  recurrence_available: boolean;
}

// PHASE-43.2 — Explicabilidad: por qué una categoría es Fija o Variable.

/** Razón por la que una categoría se clasificó estructural/puntual. */
export type StructureReason =
  | 'override_category'
  | 'rule_1_fixed_expense'
  | 'rule_2_debt_role'
  | 'rule_3_recurrence'
  | 'not_recurring'
  | 'insufficient_history';

export interface CategoryStructureExplain {
  category_id: string;
  category_name: string;
  is_structural: boolean;
  reason: StructureReason;
  /** Meses de la ventana con gasto en la categoría. */
  months_active: number;
  /** De los activos, cuántos dentro de ±banda de la mediana (regla 3). */
  months_in_band: number;
  /** Mediana de los totales mensuales activos; `null` si no hay actividad. */
  median_monthly: string | null;
  /** Nº de tx de la categoría en el rango con `is_exceptional` fijado. */
  tx_overrides: number;
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
