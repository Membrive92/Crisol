import type {
  ImportColumnMappings,
  ImportJob,
  ImportListQuery,
  ImportListResponse,
} from '@finanzas/types';

import { apiClient } from '../client';

export interface CreateImportPayload {
  file: File;
  columnMappings: ImportColumnMappings;
  currency: string;
  defaultCategoryId?: string | null;
}

export const importsApi = {
  async list(query: ImportListQuery = {}): Promise<ImportListResponse> {
    const response = await apiClient.get<ImportListResponse>('/imports', {
      params: query,
    });
    return response.data;
  },

  async get(id: string): Promise<ImportJob> {
    const response = await apiClient.get<ImportJob>(`/imports/${id}`);
    return response.data;
  },

  async create(payload: CreateImportPayload): Promise<ImportJob> {
    const formData = new FormData();
    formData.append('file', payload.file);
    formData.append('column_mappings', JSON.stringify(payload.columnMappings));
    formData.append('currency', payload.currency);
    if (payload.defaultCategoryId) {
      formData.append('default_category_id', payload.defaultCategoryId);
    }

    const response = await apiClient.post<ImportJob>('/imports', formData);
    return response.data;
  },
};
