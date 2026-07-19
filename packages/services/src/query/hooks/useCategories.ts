import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type {
  Category,
  CategoryCreateRequest,
  CategoryUpdateRequest,
} from '@crisol/types';

import { categoriesApi } from '../../api/endpoints/categories';
import { queryKeys } from '../keys';

export function useCategories() {
  return useQuery({
    queryKey: queryKeys.categories.list(),
    queryFn: () => categoriesApi.list(),
    staleTime: 1000 * 60 * 5,
  });
}

export function useCategory(id: string | undefined) {
  return useQuery({
    queryKey: id ? queryKeys.categories.detail(id) : queryKeys.categories.all,
    queryFn: () => categoriesApi.get(id as string),
    enabled: !!id,
  });
}

export function useCreateCategory() {
  const queryClient = useQueryClient();
  return useMutation<Category, Error, CategoryCreateRequest>({
    mutationFn: (data) => categoriesApi.create(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.categories.all });
    },
  });
}

export function useUpdateCategory(id: string) {
  const queryClient = useQueryClient();
  return useMutation<Category, Error, CategoryUpdateRequest>({
    mutationFn: (data) => categoriesApi.update(id, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.categories.all });
      // PHASE-43.2: `expense_nature` cambia la clasificación estructural/puntual
      // → el desglose y la tasa de ahorro estructural deben recomputarse.
      void queryClient.invalidateQueries({ queryKey: queryKeys.analytics.all });
    },
  });
}

export function useDeleteCategory() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) => categoriesApi.remove(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.categories.all });
    },
  });
}
