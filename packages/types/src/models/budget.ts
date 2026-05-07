/**
 * Tipos del módulo `budgets` (PHASE-12.1 backend, PHASE-12.2 frontend).
 *
 * Importes vienen como `string` (Decimal serializado) para preservar
 * precisión — frontend convierte con `Number(...)` o `Decimal.js` si
 * necesita aritmética.
 */

export type BudgetStatus = 'ok' | 'warning' | 'over';

export interface Budget {
  id: string;
  user_id: string;
  category_id: string | null;
  amount: string;
  currency: string;
  /** ISO date `YYYY-MM-DD`. */
  effective_from: string;
  /** ISO date o null (vigente). */
  effective_to: string | null;
  /**
   * PHASE-16: opt-in cross-currency. Cuando `true`, el status del
   * budget suma también las txs en otras monedas convirtiéndolas a
   * `currency` con la tasa del día de la tx. `false` (default)
   * mantiene el comportamiento legacy (sólo misma currency).
   */
  convert_other_currencies: boolean;
  created_at: string;
  updated_at: string;
}

export interface BudgetStatusItem {
  budget: Budget;
  spent_this_month: string;
  remaining: string;
  /** 0..∞ — frontend cap a 100 en barra de progreso si es necesario. */
  percent_used: number;
  status: BudgetStatus;
  /**
   * PHASE-16: nº de txs en otras monedas que se quedaron fuera del
   * SUM por falta de tasa disponible. Siempre 0 cuando
   * `budget.convert_other_currencies` es false.
   */
  unconvertible_count: number;
}

export interface BudgetStatusResponse {
  items: BudgetStatusItem[];
  /** ISO date — primer día del mes UTC actual. */
  month_start: string;
  /** ISO date — último día del mes UTC actual. */
  month_end: string;
}
