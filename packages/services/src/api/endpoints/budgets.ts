import type {
  Budget,
  BudgetCreateRequest,
  BudgetStatusResponse,
  BudgetUpdateRequest,
} from '@crisol/types';

import { apiClient } from '../client';

export const budgetsApi = {
  async list(): Promise<Budget[]> {
    const response = await apiClient.get<Budget[]>('/budgets');
    return response.data;
  },

  async get(id: string): Promise<Budget> {
    const response = await apiClient.get<Budget>(`/budgets/${id}`);
    return response.data;
  },

  async status(): Promise<BudgetStatusResponse> {
    const response = await apiClient.get<BudgetStatusResponse>('/budgets/status');
    return response.data;
  },

  async create(data: BudgetCreateRequest): Promise<Budget> {
    const response = await apiClient.post<Budget>('/budgets', data);
    return response.data;
  },

  async update(id: string, data: BudgetUpdateRequest): Promise<Budget> {
    const response = await apiClient.put<Budget>(`/budgets/${id}`, data);
    return response.data;
  },

  async remove(id: string): Promise<void> {
    await apiClient.delete(`/budgets/${id}`);
  },
};
