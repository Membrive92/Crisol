import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type {
  Transaction,
  TransactionCreateRequest,
  TransactionListQuery,
  TransactionUpdateRequest,
} from '@finanzas/types';

import { transactionsApi } from '../../api/endpoints/transactions';
import { queryKeys } from '../keys';

export function useTransactions(query: TransactionListQuery = {}) {
  return useQuery({
    queryKey: queryKeys.transactions.list(query),
    queryFn: () => transactionsApi.list(query),
    placeholderData: (previous) => previous,
  });
}

export function useTransaction(id: string | undefined) {
  return useQuery({
    queryKey: id ? queryKeys.transactions.detail(id) : queryKeys.transactions.all,
    queryFn: () => transactionsApi.get(id as string),
    enabled: !!id,
  });
}

export function useCreateTransaction() {
  const queryClient = useQueryClient();
  return useMutation<Transaction, Error, TransactionCreateRequest>({
    mutationFn: (data) => transactionsApi.create(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.transactions.all });
    },
  });
}

export function useUpdateTransaction(id: string) {
  const queryClient = useQueryClient();
  return useMutation<Transaction, Error, TransactionUpdateRequest>({
    mutationFn: (data) => transactionsApi.update(id, data),
    onSuccess: (updated) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.transactions.all });
      queryClient.setQueryData(queryKeys.transactions.detail(updated.id), updated);
    },
  });
}

export function useDeleteTransaction() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) => transactionsApi.remove(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.transactions.all });
    },
  });
}
