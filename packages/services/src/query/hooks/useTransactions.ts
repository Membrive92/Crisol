import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type {
  Transaction,
  TransactionCreateRequest,
  TransactionListQuery,
  TransactionUpdateRequest,
} from '@crisol/types';
// PHASE-14.5: el hook dispara un toast cuando la respuesta del POST
// trae `budget_alert`. La store de toasts es cross-platform y
// `toast.warning` / `toast.error` ya tienen palette por kind.
import { toast } from '@crisol/store';

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

/**
 * Periodos (año + meses con datos) en los que el usuario tiene
 * transacciones activas. Alimenta el selector rápido de la toolbar
 * para que no muestre años ni meses vacíos. Se invalida implícitamente
 * con el resto del grupo `transactions.all` al crear/borrar/restaurar.
 */
/**
 * PHASE-31.3 — conteo + suma de tx sin categoría. Refresca con cada
 * crear/borrar/categorizar tx (invalidación del grupo `transactions.all`).
 */
export function useUncategorizedSummary() {
  return useQuery<
    { count: number; total_amount: string; currency: string },
    Error
  >({
    queryKey: queryKeys.transactions.uncategorizedSummary(),
    queryFn: () => transactionsApi.uncategorizedSummary(),
    staleTime: 1000 * 30,
  });
}

export function useTransactionAvailablePeriods() {
  return useQuery<{ year: number; months: number[] }[], Error>({
    queryKey: queryKeys.transactions.availablePeriods(),
    queryFn: () => transactionsApi.availablePeriods(),
    staleTime: 1000 * 60 * 5,
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
        // PHASE-15.1: dedupKey por budget evita spam si el usuario
        // crea varias txs seguidas en la misma categoría — el toast
        // se reemplaza en su sitio en lugar de apilarse.
        toast.show({
          kind: alert.status === 'over' ? 'error' : 'warning',
          message: alert.next_due_label,
          dedupKey: `budget:${alert.budget_id}`,
        });
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

/**
 * Bulk soft-delete: mueve a papelera todas las transacciones que
 * matcheen los filtros pasados (los mismos del listado). Sin filtros,
 * mueve todas las activas. Mismo blast radius que `useDeleteTransaction`.
 */
export function useBulkDeleteTransactions() {
  const queryClient = useQueryClient();
  return useMutation<{ deleted_count: number }, Error, TransactionListQuery>({
    mutationFn: (query) => transactionsApi.bulkRemove(query),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.transactions.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.budgets.all });
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

/**
 * Restaura todas las transacciones que el usuario tiene en papelera.
 * Mismo blast radius que `useRestoreTransaction` pero sin id.
 */
export function useBulkRestoreTrash() {
  const queryClient = useQueryClient();
  return useMutation<{ restored_count: number }, Error, void>({
    mutationFn: () => transactionsApi.bulkRestoreTrash(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.transactions.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.budgets.all });
    },
  });
}

/**
 * Borra permanente (DELETE real) todas las transacciones que el
 * usuario tiene en papelera. IRREVERSIBLE.
 */
export function useBulkPurgeTrash() {
  const queryClient = useQueryClient();
  return useMutation<{ purged_count: number }, Error, void>({
    mutationFn: () => transactionsApi.bulkPurgeTrash(),
    onSuccess: () => {
      // Sólo desaparecen de la papelera; ni listado ni dashboard las
      // veían ya. Suficiente con invalidar `transactions.all`.
      void queryClient.invalidateQueries({ queryKey: queryKeys.transactions.all });
    },
  });
}
