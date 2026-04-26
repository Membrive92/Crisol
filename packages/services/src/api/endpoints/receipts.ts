import type {
  Receipt,
  ReceiptConfirmRequest,
  ReceiptExtractResponse,
  ReceiptListQuery,
  ReceiptListResponse,
} from '@finanzas/types';

import { apiClient } from '../client';

export const receiptsApi = {
  async list(query: ReceiptListQuery = {}): Promise<ReceiptListResponse> {
    const response = await apiClient.get<ReceiptListResponse>('/receipts', {
      params: query,
    });
    return response.data;
  },

  async get(id: string): Promise<Receipt> {
    const response = await apiClient.get<Receipt>(`/receipts/${id}`);
    return response.data;
  },

  async extract(file: File): Promise<ReceiptExtractResponse> {
    const formData = new FormData();
    formData.append('file', file);
    const response = await apiClient.post<ReceiptExtractResponse>(
      '/receipts/extract',
      formData,
    );
    return response.data;
  },

  async confirm(id: string, payload: ReceiptConfirmRequest): Promise<Receipt> {
    const response = await apiClient.post<Receipt>(
      `/receipts/${id}/confirm`,
      payload,
    );
    return response.data;
  },

  async reject(id: string): Promise<Receipt> {
    const response = await apiClient.post<Receipt>(`/receipts/${id}/reject`);
    return response.data;
  },
};
