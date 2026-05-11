import type {
  CategoryRule,
  CategoryRuleCreateRequest,
  CategoryRuleUpdateRequest,
  SeedResult,
} from '@crisol/types';

import { apiClient } from '../client';

export const categoryRulesApi = {
  async list(): Promise<CategoryRule[]> {
    const response = await apiClient.get<{ items: CategoryRule[] }>(
      '/category-rules',
    );
    return response.data.items;
  },

  async create(data: CategoryRuleCreateRequest): Promise<CategoryRule> {
    const response = await apiClient.post<CategoryRule>('/category-rules', data);
    return response.data;
  },

  async update(
    id: string,
    data: CategoryRuleUpdateRequest,
  ): Promise<CategoryRule> {
    const response = await apiClient.put<CategoryRule>(
      `/category-rules/${id}`,
      data,
    );
    return response.data;
  },

  async remove(id: string): Promise<void> {
    await apiClient.delete(`/category-rules/${id}`);
  },

  /**
   * Crea categorías y reglas recomendadas (idempotente). Útil para
   * usuarios existentes que quieran tener el seed sin re-registrarse.
   */
  async seedRecommended(): Promise<SeedResult> {
    const response = await apiClient.post<SeedResult>('/seed/recommended');
    return response.data;
  },
};
