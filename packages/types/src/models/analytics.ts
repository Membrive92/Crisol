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
