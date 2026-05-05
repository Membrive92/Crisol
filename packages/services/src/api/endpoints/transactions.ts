import type {
  Transaction,
  TransactionCreateRequest,
  TransactionListQuery,
  TransactionListResponse,
  TransactionUpdateRequest,
} from '@finanzas/types';

import { apiClient } from '../client';

export const transactionsApi = {
  async list(query: TransactionListQuery = {}): Promise<TransactionListResponse> {
    const response = await apiClient.get<TransactionListResponse>('/transactions', {
      params: query,
    });
    return response.data;
  },

  async get(id: string): Promise<Transaction> {
    const response = await apiClient.get<Transaction>(`/transactions/${id}`);
    return response.data;
  },

  async create(data: TransactionCreateRequest): Promise<Transaction> {
    const response = await apiClient.post<Transaction>('/transactions', data);
    return response.data;
  },

  async update(id: string, data: TransactionUpdateRequest): Promise<Transaction> {
    const response = await apiClient.put<Transaction>(`/transactions/${id}`, data);
    return response.data;
  },

  async remove(id: string): Promise<void> {
    await apiClient.delete(`/transactions/${id}`);
  },

  // PHASE-10.1 — papelera (soft-delete).
  async listTrash(query: { limit?: number; offset?: number } = {}): Promise<TransactionListResponse> {
    const response = await apiClient.get<TransactionListResponse>(
      '/transactions/trash',
      { params: query },
    );
    return response.data;
  },

  async restore(id: string): Promise<Transaction> {
    const response = await apiClient.post<Transaction>(
      `/transactions/${id}/restore`,
    );
    return response.data;
  },

  async purge(id: string): Promise<void> {
    await apiClient.delete(`/transactions/${id}/purge`);
  },
};
