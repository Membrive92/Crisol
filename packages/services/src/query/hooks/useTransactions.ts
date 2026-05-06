import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type {
  Transaction,
  TransactionCreateRequest,
  TransactionListQuery,
  TransactionUpdateRequest,
} from '@finanzas/types';
// PHASE-14.5: el hook dispara un toast cuando la respuesta del POST
// trae `budget_alert`. La store de toasts es cross-platform y
// `toast.warning` / `toast.error` ya tienen palette por kind.
import { toast } from '@finanzas/store';

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
    onSuccess: (created) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.transactions.all });
      // Crear afecta budgets — invalidamos el grupo entero para que
      // los status cards refresquen sin esperar al staleTime.
      void queryClient.invalidateQueries({ queryKey: queryKeys.budgets.all });
      // PHASE-14.5: notificación proactiva si la nueva tx empuja a
      // warning/over. El backend prepara `next_due_label` listo
      // para el toast.
      const alert = created.budget_alert;
      if (alert) {
        if (alert.status === 'over') {
          toast.error(alert.next_due_label);
        } else {
          toast.warning(alert.next_due_label);
        }
      }
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
      // Soft-delete (PHASE-10.1) — la fila se va de list/dashboard y
      // aparece en trash. Invalidamos `transactions.all` (cubre list,
      // trash y detail) y `dashboard.all` para que summary/top-expenses
      // se actualicen sin esperar a staleTime.
      void queryClient.invalidateQueries({ queryKey: queryKeys.transactions.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
    },
  });
}

export function useTrashedTransactions(query: { limit?: number; offset?: number } = {}) {
  return useQuery({
    queryKey: queryKeys.transactions.trash(query),
    queryFn: () => transactionsApi.listTrash(query),
    placeholderData: (previous) => previous,
  });
}

export function useRestoreTransaction() {
  const queryClient = useQueryClient();
  return useMutation<Transaction, Error, string>({
    mutationFn: (id) => transactionsApi.restore(id),
    onSuccess: () => {
      // Vuelve a list/dashboard, sale de trash. Mismo blast radius
      // que delete pero al revés.
      void queryClient.invalidateQueries({ queryKey: queryKeys.transactions.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
    },
  });
}

export function usePurgeTransaction() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) => transactionsApi.purge(id),
    onSuccess: () => {
      // Sólo afecta a la papelera (la tx ya estaba excluida de list y
      // dashboard). Aun así invalidamos `transactions.all` para que
      // el contador y la lista de papelera se refresquen.
      void queryClient.invalidateQueries({ queryKey: queryKeys.transactions.all });
    },
  });
}
