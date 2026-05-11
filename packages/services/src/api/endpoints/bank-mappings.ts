import type { BankCategoryMapping } from '@crisol/types';

import { apiClient } from '../client';

export interface BankMappingUpsertPayload {
  bankConcept: string;
  categoryId: string;
}

export const bankMappingsApi = {
  async list(): Promise<BankCategoryMapping[]> {
    const response = await apiClient.get<{ items: BankCategoryMapping[] }>(
      '/bank-mappings',
    );
    return response.data.items;
  },

  /** Crea o actualiza la equivalencia (UPSERT por bank_concept). */
  async upsert(payload: BankMappingUpsertPayload): Promise<BankCategoryMapping> {
    const response = await apiClient.post<BankCategoryMapping>('/bank-mappings', {
      bank_concept: payload.bankConcept,
      category_id: payload.categoryId,
    });
    return response.data;
  },

  async remove(id: string): Promise<void> {
    await apiClient.delete(`/bank-mappings/${id}`);
  },
};
