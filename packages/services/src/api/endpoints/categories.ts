import type {
  Category,
  CategoryCreateRequest,
  CategoryUpdateRequest,
} from '@crisol/types';

import { apiClient } from '../client';

export const categoriesApi = {
  async list(): Promise<Category[]> {
    const response = await apiClient.get<Category[]>('/categories');
    return response.data;
  },

  async get(id: string): Promise<Category> {
    const response = await apiClient.get<Category>(`/categories/${id}`);
    return response.data;
  },

  async create(data: CategoryCreateRequest): Promise<Category> {
    const response = await apiClient.post<Category>('/categories', data);
    return response.data;
  },

  async update(id: string, data: CategoryUpdateRequest): Promise<Category> {
    const response = await apiClient.put<Category>(`/categories/${id}`, data);
    return response.data;
  },

  async remove(id: string): Promise<void> {
    await apiClient.delete(`/categories/${id}`);
  },
};
