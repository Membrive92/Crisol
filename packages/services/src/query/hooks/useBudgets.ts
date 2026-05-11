import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type {
  Budget,
  BudgetCreateRequest,
  BudgetStatusResponse,
  BudgetUpdateRequest,
} from '@crisol/types';

import { budgetsApi } from '../../api/endpoints/budgets';
import { queryKeys } from '../keys';

export function useBudgets() {
  return useQuery({
    queryKey: queryKeys.budgets.list(),
    queryFn: () => budgetsApi.list(),
  });
}

export function useBudget(id: string | undefined) {
  return useQuery({
    queryKey: id ? queryKeys.budgets.detail(id) : queryKeys.budgets.all,
    queryFn: () => budgetsApi.get(id as string),
    enabled: !!id,
  });
}

export function useBudgetStatus() {
  return useQuery<BudgetStatusResponse, Error>({
    queryKey: queryKeys.budgets.status(),
    queryFn: () => budgetsApi.status(),
    placeholderData: (previous) => previous,
  });
}

export function useCreateBudget() {
  const queryClient = useQueryClient();
  return useMutation<Budget, Error, BudgetCreateRequest>({
    mutationFn: (data) => budgetsApi.create(data),
    onSuccess: () => {
      // Crear un budget afecta list, detail futuro y status — invalida todo el grupo.
      void queryClient.invalidateQueries({ queryKey: queryKeys.budgets.all });
    },
  });
}

export interface UpdateBudgetVariables {
  id: string;
  data: BudgetUpdateRequest;
}

export function useUpdateBudget() {
  const queryClient = useQueryClient();
  return useMutation<Budget, Error, UpdateBudgetVariables>({
    mutationFn: ({ id, data }) => budgetsApi.update(id, data),
    onSuccess: (updated) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.budgets.all });
      queryClient.setQueryData(queryKeys.budgets.detail(updated.id), updated);
    },
  });
}

export function useDeleteBudget() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) => budgetsApi.remove(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.budgets.all });
    },
  });
}
