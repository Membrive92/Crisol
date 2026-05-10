import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type {
  CategoryRule,
  CategoryRuleCreateRequest,
  CategoryRuleUpdateRequest,
  SeedResult,
} from '@finanzas/types';

import { categoryRulesApi } from '../../api/endpoints/category-rules';
import { queryKeys } from '../keys';

export function useCategoryRules() {
  return useQuery({
    queryKey: queryKeys.categoryRules.all,
    queryFn: () => categoryRulesApi.list(),
    placeholderData: (previous) => previous,
  });
}

export function useCreateCategoryRule() {
  const queryClient = useQueryClient();
  return useMutation<CategoryRule, Error, CategoryRuleCreateRequest>({
    mutationFn: (data) => categoryRulesApi.create(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.categoryRules.all,
      });
    },
  });
}

export function useUpdateCategoryRule(id: string) {
  const queryClient = useQueryClient();
  return useMutation<CategoryRule, Error, CategoryRuleUpdateRequest>({
    mutationFn: (data) => categoryRulesApi.update(id, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.categoryRules.all,
      });
    },
  });
}

export function useDeleteCategoryRule() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) => categoryRulesApi.remove(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.categoryRules.all,
      });
    },
  });
}

/**
 * Crea categorías y reglas recomendadas para bancos españoles.
 * Idempotente. Devuelve el resumen para mostrar en toast/UI.
 */
export function useSeedRecommended() {
  const queryClient = useQueryClient();
  return useMutation<SeedResult, Error, void>({
    mutationFn: () => categoryRulesApi.seedRecommended(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.categories.all });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.categoryRules.all,
      });
    },
  });
}
