import type {
  MisclassifiedTransfer,
  ReclassifyBulkResponse,
  TransferCandidate,
  TransferFromSourceDebtRequest,
  TransferFromSourceRequest,
  TransferLinkRequest,
  TransferMarkRequest,
  TransferMarkResponse,
  TransferMatchOptions,
  TransferMatchResponse,
  TransferPair,
  TransferSuspect,
} from '@crisol/types';

import { apiClient } from '../client';

export const transfersApi = {
  async list(): Promise<TransferPair[]> {
    const response = await apiClient.get<TransferPair[]>('/transfers');
    return response.data;
  },

  async candidates(windowDays = 3): Promise<TransferCandidate[]> {
    const response = await apiClient.get<TransferCandidate[]>(
      '/transfers/candidates',
      { params: { window_days: windowDays } },
    );
    return response.data;
  },

  async match(options: TransferMatchOptions = {}): Promise<TransferMatchResponse> {
    const response = await apiClient.post<TransferMatchResponse>(
      '/transfers/match',
      options,
    );
    return response.data;
  },

  async link(payload: TransferLinkRequest): Promise<TransferPair> {
    const response = await apiClient.post<TransferPair>(
      '/transfers/link',
      payload,
    );
    return response.data;
  },

  async unlink(transactionId: string): Promise<void> {
    await apiClient.delete(`/transfers/${transactionId}`);
  },

  async suspects(): Promise<TransferSuspect[]> {
    const response = await apiClient.get<TransferSuspect[]>(
      '/transfers/suspects',
    );
    return response.data;
  },

  async mark(payload: TransferMarkRequest): Promise<TransferMarkResponse> {
    const response = await apiClient.post<TransferMarkResponse>(
      '/transfers/mark',
      payload,
    );
    return response.data;
  },

  async fromSource(payload: TransferFromSourceRequest): Promise<TransferPair> {
    const response = await apiClient.post<TransferPair>(
      '/transfers/from-source',
      payload,
    );
    return response.data;
  },

  async fromSourceDebt(
    payload: TransferFromSourceDebtRequest,
  ): Promise<TransferPair> {
    const response = await apiClient.post<TransferPair>(
      '/transfers/from-source-debt',
      payload,
    );
    return response.data;
  },

  /** PHASE-31.2 — tx con categoría is_transfer y dirección dudosa. */
  async misclassified(): Promise<MisclassifiedTransfer[]> {
    const response = await apiClient.get<MisclassifiedTransfer[]>(
      '/transfers/misclassified',
    );
    return response.data;
  },

  /** PHASE-31.2 — recategorización en bloque. */
  async reclassifyBulk(payload: {
    transaction_ids: string[];
    target_category_id?: string;
  }): Promise<ReclassifyBulkResponse> {
    const response = await apiClient.post<ReclassifyBulkResponse>(
      '/transfers/reclassify-bulk',
      payload,
    );
    return response.data;
  },
};
