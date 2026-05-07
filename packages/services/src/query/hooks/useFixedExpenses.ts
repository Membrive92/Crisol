import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type {
  FixedExpense,
  FixedExpenseScanResponse,
  FixedExpenseStatus,
} from '@finanzas/types';

import {
  type FixedExpenseListQuery,
  fixedExpensesApi,
} from '../../api/endpoints/fixed-expenses';
import { queryKeys } from '../keys';

export function useFixedExpenses(query: FixedExpenseListQuery = {}) {
  return useQuery({
    queryKey: queryKeys.fixedExpenses.list(query.status),
    queryFn: () => fixedExpensesApi.list(query),
    placeholderData: (previous) => previous,
  });
}

export function useFixedExpense(id: string | undefined) {
  return useQuery({
    queryKey: id ? queryKeys.fixedExpenses.detail(id) : queryKeys.fixedExpenses.all,
    queryFn: () => fixedExpensesApi.get(id as string),
    enabled: !!id,
  });
}

export function useScanFixedExpenses() {
  const queryClient = useQueryClient();
  return useMutation<FixedExpenseScanResponse, Error, void>({
    mutationFn: () => fixedExpensesApi.scan(),
    onSuccess: () => {
      // Scan puede crear/refrescar todo — invalida el grupo entero.
      void queryClient.invalidateQueries({ queryKey: queryKeys.fixedExpenses.all });
    },
  });
}

export function useConfirmFixedExpense() {
  const queryClient = useQueryClient();
  return useMutation<FixedExpense, Error, string>({
    mutationFn: (id) => fixedExpensesApi.confirm(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.fixedExpenses.all });
    },
  });
}

export function useDismissFixedExpense() {
  const queryClient = useQueryClient();
  return useMutation<FixedExpense, Error, string>({
    mutationFn: (id) => fixedExpensesApi.dismiss(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.fixedExpenses.all });
    },
  });
}

export function useDeleteFixedExpense() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) => fixedExpensesApi.remove(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.fixedExpenses.all });
    },
  });
}

export function usePauseFixedExpense() {
  const queryClient = useQueryClient();
  return useMutation<FixedExpense, Error, string>({
    mutationFn: (id) => fixedExpensesApi.pause(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.fixedExpenses.all });
    },
  });
}

export function useResumeFixedExpense() {
  const queryClient = useQueryClient();
  return useMutation<FixedExpense, Error, string>({
    mutationFn: (id) => fixedExpensesApi.resume(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.fixedExpenses.all });
    },
  });
}

export function useCancelFixedExpense() {
  const queryClient = useQueryClient();
  return useMutation<FixedExpense, Error, string>({
    mutationFn: (id) => fixedExpensesApi.cancel(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.fixedExpenses.all });
    },
  });
}

export type { FixedExpenseListQuery, FixedExpenseStatus };
