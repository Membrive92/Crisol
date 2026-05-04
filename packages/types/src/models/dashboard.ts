import type { CategoryKind } from './category';

export interface DashboardSummary {
  income: string;
  expenses: string;
  balance: string;
  transaction_count: number;
  currency: string;
  /**
   * Transacciones del rango que no se pudieron convertir a
   * `target_currency` por falta de tasa (PHASE-8.3). Sólo es > 0 en
   * modo cross-currency; en legacy siempre es 0.
   */
  unconvertible_count: number;
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
  /**
   * Importe usado para el ranking. En modo `target_currency` es el
   * convertido; en legacy coincide con `original_amount`.
   */
  amount: string;
  occurred_at: string;
  category_id: string | null;
  category_name: string | null;
  /** Importe original de la transacción, sin convertir (PHASE-8.4). */
  original_amount: string;
  /** Moneda original de la transacción (PHASE-8.4). */
  original_currency: string;
}
