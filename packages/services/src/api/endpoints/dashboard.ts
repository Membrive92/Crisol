import type {
  CategoryBreakdownItem,
  CategoryDetail,
  DashboardByCategoryQuery,
  DashboardByMonthQuery,
  DashboardCategoryDetailQuery,
  DashboardSummary,
  DashboardSummaryQuery,
  DashboardTopExpensesQuery,
  ModuleDashboardSummary,
  MonthlyBucket,
  TopExpenseItem,
} from '@crisol/types';

import { apiClient } from '../client';

/** Divisa + rango de la tarjeta de módulo (mismo patrón que el resto). */
export interface ModuleSummaryQuery {
  currency?: string;
  target_currency?: string;
  date_from?: string;
  date_to?: string;
}

export const dashboardApi = {
  async currencies(): Promise<string[]> {
    const response = await apiClient.get<string[]>('/dashboard/currencies');
    return response.data;
  },

  async moduleSummary(query: ModuleSummaryQuery = {}): Promise<ModuleDashboardSummary> {
    const response = await apiClient.get<ModuleDashboardSummary>(
      '/dashboard/module-summary',
      { params: query },
    );
    return response.data;
  },

  async summary(query: DashboardSummaryQuery = {}): Promise<DashboardSummary> {
    const response = await apiClient.get<DashboardSummary>('/dashboard/summary', {
      params: query,
    });
    return response.data;
  },

  async byCategory(query: DashboardByCategoryQuery = {}): Promise<CategoryBreakdownItem[]> {
    const response = await apiClient.get<CategoryBreakdownItem[]>('/dashboard/by-category', {
      params: query,
    });
    return response.data;
  },

  async byMonth(query: DashboardByMonthQuery = {}): Promise<MonthlyBucket[]> {
    const response = await apiClient.get<MonthlyBucket[]>('/dashboard/by-month', {
      params: query,
    });
    return response.data;
  },

  async topExpenses(query: DashboardTopExpensesQuery = {}): Promise<TopExpenseItem[]> {
    const response = await apiClient.get<TopExpenseItem[]>('/dashboard/top-expenses', {
      params: query,
    });
    return response.data;
  },

  async categoryDetail(
    categoryId: string,
    query: DashboardCategoryDetailQuery = {},
  ): Promise<CategoryDetail> {
    const response = await apiClient.get<CategoryDetail>(
      `/dashboard/category/${categoryId}`,
      { params: query },
    );
    return response.data;
  },

  async categoryAvailablePeriods(
    categoryId: string,
  ): Promise<{ year: number; months: number[] }[]> {
    const response = await apiClient.get<{
      periods: { year: number; months: number[] }[];
    }>(`/dashboard/category/${categoryId}/available-periods`);
    return response.data.periods;
  },
};
