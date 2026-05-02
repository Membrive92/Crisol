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
    // La inferencia local con qwen2.5vl en CPU puede tardar 60-120s en frío.
    // El backend tiene 120s de timeout contra Ollama, así que damos 180s aquí
    // para cubrir tanto la inferencia como el round-trip + persistencia.
    const response = await apiClient.post<ReceiptExtractResponse>(
      '/receipts/extract',
      formData,
      { timeout: 180_000 },
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

  async getBlob(id: string): Promise<Blob> {
    const response = await apiClient.get<Blob>(`/receipts/${id}/blob`, {
      responseType: 'blob',
    });
    return response.data;
  },
};
