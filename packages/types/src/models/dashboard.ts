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
  /**
   * PHASE-37.1 — Δ vs periodo anterior equivalente. `cashflow_delta` =
   * `balance − previous_period_balance`; `savings_rate_delta_pp` = variación
   * de la tasa de ahorro en puntos porcentuales. `null` sin periodo previo.
   */
  cashflow_delta: string | null;
  savings_rate_delta_pp: number | null;
  /**
   * PHASE-34 — Mes (`YYYY-MM`) más antiguo / más reciente con transacciones
   * del usuario, global (ignora el filtro de período). Acotan las flechas del
   * navegador de período en Análisis. `null` si no hay transacciones.
   */
  available_from: string | null;
  available_to: string | null;
}

export interface CategoryBreakdownItem {
  category_id: string | null;
  category_name: string;
  category_kind: CategoryKind | null;
  category_color: string | null;
  category_icon: string | null;
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

export interface CategoryMonthlyBucket {
  month: string;
  total: string;
}

/**
 * PHASE-25 — Drill-down de una categoría desde el "Desglose de
 * gastos" del dashboard. KPIs + evolución mensual + top tx.
 */
export interface CategoryDetail {
  category_id: string;
  category_name: string;
  category_kind: CategoryKind;
  category_color: string | null;
  category_icon: string | null;
  currency: string;
  /** Total del rango (en `currency`). */
  total: string;
  /** Número de tx en el rango. */
  count: number;
  /** Ticket medio (`total / count`). */
  average_amount: string;
  /** Evolución mensual (cronológica). */
  by_month: CategoryMonthlyBucket[];
  /** Top 10 tx por importe en el rango. */
  top_transactions: TopExpenseItem[];
}
