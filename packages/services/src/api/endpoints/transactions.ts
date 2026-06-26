import type {
  Transaction,
  TransactionCreateRequest,
  TransactionListQuery,
  TransactionListResponse,
  TransactionUpdateRequest,
} from '@crisol/types';

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

  /**
   * Bulk soft-delete: mueve a papelera todas las transacciones que matcheen
   * los filtros pasados. Acepta los mismos filtros que `list`. Sin filtros
   * (objeto vacío) borra todas las activas del usuario.
   */
  async bulkRemove(query: TransactionListQuery = {}): Promise<{ deleted_count: number }> {
    const response = await apiClient.delete<{ deleted_count: number }>('/transactions', {
      params: query,
    });
    return response.data;
  },

  /**
   * PHASE-32 — Reasigna en bloque a `targetAccountId` las transacciones
   * activas que matcheen `filters` (mismos que `list`). Excluye
   * transferencias internas. Para consolidar p. ej. "el mes en BBVA".
   */
  async reassignAccount(
    targetAccountId: string,
    filters: TransactionListQuery = {},
  ): Promise<{ reassigned_count: number; skipped_other_currency: number }> {
    const response = await apiClient.post<{
      reassigned_count: number;
      skipped_other_currency: number;
    }>('/transactions/reassign-account', {
      target_account_id: targetAccountId,
      ...filters,
    });
    return response.data;
  },

  // PHASE-10.1 — papelera (soft-delete).
  async listTrash(
    query: { limit?: number; offset?: number } = {},
  ): Promise<TransactionListResponse> {
    const response = await apiClient.get<TransactionListResponse>('/transactions/trash', {
      params: query,
    });
    return response.data;
  },

  async restore(id: string): Promise<Transaction> {
    const response = await apiClient.post<Transaction>(`/transactions/${id}/restore`);
    return response.data;
  },

  async purge(id: string): Promise<void> {
    await apiClient.delete(`/transactions/${id}/purge`);
  },

  /** Restaura todas las transacciones del usuario que estén en papelera. */
  async bulkRestoreTrash(): Promise<{ restored_count: number }> {
    const response = await apiClient.post<{ restored_count: number }>(
      '/transactions/trash/restore',
    );
    return response.data;
  },

  /**
   * Borra permanente (DELETE real) todo lo que el usuario tenga en
   * papelera. IRREVERSIBLE — el caller debe confirmar antes.
   */
  async bulkPurgeTrash(): Promise<{ purged_count: number }> {
    const response = await apiClient.delete<{ purged_count: number }>('/transactions/trash');
    return response.data;
  },

  /**
   * PHASE-31.3 — conteo + suma de tx sin categoría. Alimenta el
   * banner que invita a categorizar. Las tx sin categoría ya no
   * contaminan el saldo (`else_=0`), así que conviene que el
   * usuario las vea para no perderlas de vista.
   */
  async uncategorizedSummary(): Promise<{
    count: number;
    total_amount: string;
    currency: string;
  }> {
    const response = await apiClient.get<{
      count: number;
      total_amount: string;
      currency: string;
    }>('/transactions/uncategorized-summary');
    return response.data;
  },

  /**
   * Años + meses con transacciones activas del usuario. Los años
   * llegan en orden descendente; los meses dentro de cada año en
   * orden ascendente (1-12). Vacío si el usuario aún no tiene
   * transacciones.
   */
  async availablePeriods(): Promise<{ year: number; months: number[] }[]> {
    const response = await apiClient.get<{
      periods: { year: number; months: number[] }[];
    }>('/transactions/available-periods');
    return response.data.periods;
  },
};
