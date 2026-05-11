import type {
  FixedExpense,
  FixedExpenseScanResponse,
  FixedExpenseStatus,
} from '@crisol/types';

import { apiClient } from '../client';

export interface FixedExpenseListQuery {
  status?: FixedExpenseStatus;
}

export interface FixedExpenseUpdatePayload {
  auto_post?: boolean;
  /** PHASE-19.1: cuenta de cobro. `null` desactiva el autopost (sin cuenta no se puede crear la tx). */
  account_id?: string | null;
}

export interface AutopostResponse {
  created: number;
  advanced: number;
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

  async update(id: string, data: FixedExpenseUpdatePayload): Promise<FixedExpense> {
    const response = await apiClient.put<FixedExpense>(
      `/fixed-expenses/${id}`,
      data,
    );
    return response.data;
  },

  async scan(): Promise<FixedExpenseScanResponse> {
    const response = await apiClient.post<FixedExpenseScanResponse>(
      '/fixed-expenses/scan',
    );
    return response.data;
  },

  async autopost(): Promise<AutopostResponse> {
    const response = await apiClient.post<AutopostResponse>(
      '/fixed-expenses/autopost',
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
