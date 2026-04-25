import type {
  CategoryBreakdownItem,
  DashboardByCategoryQuery,
  DashboardByMonthQuery,
  DashboardSummary,
  DashboardSummaryQuery,
  DashboardTopExpensesQuery,
  MonthlyBucket,
  TopExpenseItem,
} from '@finanzas/types';

import { apiClient } from '../client';

export const dashboardApi = {
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
};
