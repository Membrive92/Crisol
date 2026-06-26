import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type {
  FixedExpense,
  FixedExpenseScanResponse,
  FixedExpenseStatus,
} from '@crisol/types';

import {
  type AutopostResponse,
  type FixedExpenseListQuery,
  type FixedExpenseUpdatePayload,
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
      void queryClient.invalidateQueries({ queryKey: queryKeys.debt.all });
    },
  });
}

export function useAutopostFixedExpenses() {
  const queryClient = useQueryClient();
  return useMutation<AutopostResponse, Error, void>({
    mutationFn: () => fixedExpensesApi.autopost(),
    onSuccess: () => {
      // Autopost crea transacciones y avanza next_due — invalida ambos.
      void queryClient.invalidateQueries({ queryKey: queryKeys.fixedExpenses.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.debt.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.transactions.all });
    },
  });
}

export function useUpdateFixedExpense() {
  const queryClient = useQueryClient();
  return useMutation<
    FixedExpense,
    Error,
    { id: string; data: FixedExpenseUpdatePayload }
  >({
    mutationFn: ({ id, data }) => fixedExpensesApi.update(id, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.fixedExpenses.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.debt.all });
    },
  });
}

export function useConfirmFixedExpense() {
  const queryClient = useQueryClient();
  return useMutation<FixedExpense, Error, string>({
    mutationFn: (id) => fixedExpensesApi.confirm(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.fixedExpenses.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.debt.all });
    },
  });
}

export function useDismissFixedExpense() {
  const queryClient = useQueryClient();
  return useMutation<FixedExpense, Error, string>({
    mutationFn: (id) => fixedExpensesApi.dismiss(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.fixedExpenses.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.debt.all });
    },
  });
}

export function useDeleteFixedExpense() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) => fixedExpensesApi.remove(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.fixedExpenses.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.debt.all });
    },
  });
}

export function usePauseFixedExpense() {
  const queryClient = useQueryClient();
  return useMutation<FixedExpense, Error, string>({
    mutationFn: (id) => fixedExpensesApi.pause(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.fixedExpenses.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.debt.all });
    },
  });
}

export function useResumeFixedExpense() {
  const queryClient = useQueryClient();
  return useMutation<FixedExpense, Error, string>({
    mutationFn: (id) => fixedExpensesApi.resume(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.fixedExpenses.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.debt.all });
    },
  });
}

export function useCancelFixedExpense() {
  const queryClient = useQueryClient();
  return useMutation<FixedExpense, Error, string>({
    mutationFn: (id) => fixedExpensesApi.cancel(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.fixedExpenses.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.debt.all });
    },
  });
}

export type { FixedExpenseListQuery, FixedExpenseStatus };
