import type {
  TransferCandidate,
  TransferLinkRequest,
  TransferMatchOptions,
  TransferMatchResponse,
  TransferPair,
} from '@finanzas/types';

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
};
