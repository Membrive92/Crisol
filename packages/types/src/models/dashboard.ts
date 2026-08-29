import type { CategoryKind } from './category';
import type { TransactionFlow } from './transaction';

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
   * PHASE-47.E2 — parte del gasto del periodo que quedó APLAZADA porque el
   * banco financió el recibo de una tarjeta.
   *
   * NO está incluida en `expenses`: el resultado del mes mide caja y ese
   * dinero no salió (sale como cuota, durante los años siguientes). SÍ está
   * en el desglose por categorías, porque el gasto se hizo.
   *
   * Es decir: es exactamente la diferencia entre las dos cifras, y hay que
   * pintarla. Sin ella, quien intente cuadrarlas a mano no puede y la
   * pantalla estaría mintiendo por omisión.
   */
  deferred_expenses: string;
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
  /**
   * PHASE-47.E4 — la parte de `total` que quedó APLAZADA por un recibo
   * financiado, para que el desglose pueda marcar QUÉ filas lo explican.
   *
   * **Opcional a propósito**: un backend anterior al campo no lo manda, y
   * tratar su ausencia como `0` afirmaría «aquí no hay nada aplazado».
   */
  deferred_total?: string | null | undefined;
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
  /**
   * PHASE-47.H — dirección del movimiento, para que la lista pueda pintar su
   * polaridad. Una devolución (`IN` en una categoría de gasto) RESTA de su
   * categoría, y sin esto la columna no sumaba el total de la pantalla.
   *
   * **Opcional a propósito**: un backend anterior a este campo no lo manda, y
   * el tipo tiene que describir lo que puede llegar, no lo que emite el
   * servidor de hoy ([PHASE-44.16]).
   */
  flow?: TransactionFlow | null;
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

/**
 * PHASE-43.4 (ADR-0006) — tarjeta de un módulo en el dashboard:
 * `veredicto + un número + un link`. El dashboard COMPONE estas tarjetas;
 * el detalle vive en la superficie del módulo (a la que apunta `link`).
 */
export type ModuleVerdict = 'healthy' | 'caution' | 'stressed' | 'neutral';

export interface ModuleSummaryItem {
  label: string;
  value: string;
}

export interface ModuleDashboardSummary {
  verdict: ModuleVerdict;
  /** El número grande, con signo (flujo del mes, −deuda viva…). */
  headline_value: string;
  headline_label: string;
  currency: string;
  secondary: ModuleSummaryItem[];
  link: string;
}
