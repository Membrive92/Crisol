import type { ExpenseStructureQuery, ExpenseStructureResponse } from '@crisol/types';

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
};
