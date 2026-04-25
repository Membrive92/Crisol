import type { CategoryKind } from '../models/category';

export interface DashboardSummaryQuery {
  currency?: string;
  date_from?: string;
  date_to?: string;
}

export interface DashboardByCategoryQuery {
  currency?: string;
  date_from?: string;
  date_to?: string;
  kind?: CategoryKind;
}

export interface DashboardByMonthQuery {
  year?: number;
  currency?: string;
}

export interface DashboardTopExpensesQuery {
  currency?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
}
