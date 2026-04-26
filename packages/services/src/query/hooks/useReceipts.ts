import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type {
  Receipt,
  ReceiptConfirmRequest,
  ReceiptExtractResponse,
  ReceiptListQuery,
} from '@finanzas/types';

import { receiptsApi } from '../../api/endpoints/receipts';
import { queryKeys } from '../keys';

export function useReceipts(query: ReceiptListQuery = {}) {
  return useQuery({
    queryKey: queryKeys.receipts.list(query),
    queryFn: () => receiptsApi.list(query),
    placeholderData: (previous) => previous,
  });
}

export function useReceipt(id: string | undefined) {
  return useQuery({
    queryKey: id ? queryKeys.receipts.detail(id) : queryKeys.receipts.all,
    queryFn: () => receiptsApi.get(id as string),
    enabled: !!id,
  });
}

export function useExtractReceipt() {
  const queryClient = useQueryClient();
  return useMutation<ReceiptExtractResponse, Error, File>({
    mutationFn: (file) => receiptsApi.extract(file),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.receipts.all });
    },
  });
}

export function useConfirmReceipt(id: string) {
  const queryClient = useQueryClient();
  return useMutation<Receipt, Error, ReceiptConfirmRequest>({
    mutationFn: (payload) => receiptsApi.confirm(id, payload),
    onSuccess: (updated) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.receipts.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.transactions.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
      queryClient.setQueryData(queryKeys.receipts.detail(updated.id), updated);
    },
  });
}

export function useRejectReceipt(id: string) {
  const queryClient = useQueryClient();
  return useMutation<Receipt, Error, void>({
    mutationFn: () => receiptsApi.reject(id),
    onSuccess: (updated) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.receipts.all });
      queryClient.setQueryData(queryKeys.receipts.detail(updated.id), updated);
    },
  });
}
