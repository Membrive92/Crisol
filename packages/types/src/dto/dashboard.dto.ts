import type { CategoryKind } from '../models/category';

// `target_currency` (PHASE-8.3): convierte cada transacción a esta
// moneda con la tasa del día de su `occurred_at` antes de agregar.
// `currency` (legacy): filtra por esa moneda y agrega importes crudos.
// Si llegan ambos, gana `target_currency`.

export interface DashboardSummaryQuery {
  currency?: string;
  target_currency?: string;
  date_from?: string;
  date_to?: string;
}

export interface DashboardByCategoryQuery {
  currency?: string;
  target_currency?: string;
  date_from?: string;
  date_to?: string;
  kind?: CategoryKind;
}

export interface DashboardByMonthQuery {
  year?: number;
  currency?: string;
  target_currency?: string;
}

export interface DashboardTopExpensesQuery {
  currency?: string;
  target_currency?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
}

/** PHASE-25 — Query del drill-down de categoría. */
export interface DashboardCategoryDetailQuery {
  currency?: string;
  target_currency?: string;
  date_from?: string;
  date_to?: string;
  /** Cuántos meses de evolución incluir (1-36, default 12). */
  months_back?: number;
}
