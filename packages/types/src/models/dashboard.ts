import type { CategoryKind } from './category';

export interface DashboardSummary {
  income: string;
  expenses: string;
  balance: string;
  transaction_count: number;
  currency: string;
  /**
   * Totales del periodo previo de igual longitud (terminando justo antes
   * de `date_from`). El backend los devuelve cuando el caller pasa
   * `date_from` y `date_to`; sin rango, los tres son `null`.
   */
  previous_period_income: string | null;
  previous_period_expenses: string | null;
  previous_period_balance: string | null;
}

export interface CategoryBreakdownItem {
  category_id: string | null;
  category_name: string;
  category_kind: CategoryKind | null;
  total: string;
  count: number;
}

export interface MonthlyBucket {
  month: string;
  income: string;
  expenses: string;
  balance: string;
}

export interface TopExpenseItem {
  transaction_id: string;
  description: string | null;
  amount: string;
  occurred_at: string;
  category_id: string | null;
  category_name: string | null;
}
