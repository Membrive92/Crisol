import type {
  ExpenseStructureQuery,
  ExpenseStructureResponse,
  MonthOutlookQuery,
  MonthOutlookResponse,
} from '@crisol/types';

import { apiClient } from '../client';

export const analyticsApi = {
  async expenseStructure(
    query: ExpenseStructureQuery = {},
  ): Promise<ExpenseStructureResponse> {
    const response = await apiClient.get<ExpenseStructureResponse>(
      '/analytics/expense-structure',
      { params: query },
    );
    return response.data;
  },

  async monthOutlook(query: MonthOutlookQuery = {}): Promise<MonthOutlookResponse> {
    const response = await apiClient.get<MonthOutlookResponse>('/analytics/month-outlook', {
      params: query,
    });
    return response.data;
  },
};
