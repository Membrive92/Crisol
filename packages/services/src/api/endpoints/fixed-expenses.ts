import type {
  FixedExpense,
  FixedExpenseScanResponse,
  FixedExpenseStatus,
} from '@finanzas/types';

import { apiClient } from '../client';

export interface FixedExpenseListQuery {
  status?: FixedExpenseStatus;
}

export const fixedExpensesApi = {
  async list(query: FixedExpenseListQuery = {}): Promise<FixedExpense[]> {
    const response = await apiClient.get<FixedExpense[]>('/fixed-expenses', {
      params: query,
    });
    return response.data;
  },

  async get(id: string): Promise<FixedExpense> {
    const response = await apiClient.get<FixedExpense>(`/fixed-expenses/${id}`);
    return response.data;
  },

  async scan(): Promise<FixedExpenseScanResponse> {
    const response = await apiClient.post<FixedExpenseScanResponse>(
      '/fixed-expenses/scan',
    );
    return response.data;
  },

  async confirm(id: string): Promise<FixedExpense> {
    const response = await apiClient.post<FixedExpense>(
      `/fixed-expenses/${id}/confirm`,
    );
    return response.data;
  },

  async dismiss(id: string): Promise<FixedExpense> {
    const response = await apiClient.post<FixedExpense>(
      `/fixed-expenses/${id}/dismiss`,
    );
    return response.data;
  },

  async pause(id: string): Promise<FixedExpense> {
    const response = await apiClient.post<FixedExpense>(
      `/fixed-expenses/${id}/pause`,
    );
    return response.data;
  },

  async resume(id: string): Promise<FixedExpense> {
    const response = await apiClient.post<FixedExpense>(
      `/fixed-expenses/${id}/resume`,
    );
    return response.data;
  },

  async cancel(id: string): Promise<FixedExpense> {
    const response = await apiClient.post<FixedExpense>(
      `/fixed-expenses/${id}/cancel`,
    );
    return response.data;
  },

  async remove(id: string): Promise<void> {
    await apiClient.delete(`/fixed-expenses/${id}`);
  },
};
