import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type {
  Transaction,
  TransactionCreateRequest,
  TransactionListQuery,
  TransactionUpdateRequest,
} from '@crisol/types';

import { transactionsApi } from '../../api/endpoints/transactions';
import { invalidateTransactionSideEffects } from '../invalidate';
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
  return useQuery<{ count: number; total_amount: string; currency: string }, Error>({
    queryKey: queryKeys.transactions.uncategorizedSummary(),
    queryFn: () => transactionsApi.uncategorizedSummary(),
    staleTime: 1000 * 30,
  });
}

export function useTransactionAvailablePeriods(cycle = false) {
  return useQuery<{ year: number; months: number[] }[], Error>({
    // El flag entra en la KEY: sin él, activar el ciclo serviría los chips
    // cacheados del mes natural y el selector volvería a mentir en silencio.
    queryKey: queryKeys.transactions.availablePeriods(cycle),
    queryFn: () => transactionsApi.availablePeriods(cycle),
    staleTime: 1000 * 60 * 5,
  });
}

/**
 * Crea una transacción. `created.budget_alert` puede venir poblado
 * (PHASE-14.5) — AUDIT-2026-05: el toast lo dispara la app en su propio
 * `onSuccess` (cada plataforma decide cómo notificar) en vez de aquí;
 * `@crisol/services` ya no importa `@crisol/store`.
 */
export function useCreateTransaction() {
  const queryClient = useQueryClient();
  return useMutation<Transaction, Error, TransactionCreateRequest>({
    mutationFn: (data) => transactionsApi.create(data),
    // AUDIT-2026-06: crear una tx mueve listado, dashboard, budgets,
    // saldos de cuenta y deuda. Antes faltaban dashboard.all y
    // accounts.all (saldos/lista de deuda quedaban stale).
    onSuccess: () => {
      invalidateTransactionSideEffects(queryClient);
    },
  });
}

export function useUpdateTransaction(id: string) {
  const queryClient = useQueryClient();
  return useMutation<Transaction, Error, TransactionUpdateRequest>({
    mutationFn: (data) => transactionsApi.update(id, data),
    // AUDIT-2026-06: editar una tx puede cambiar importe, cuenta o
    // categoría → afecta dashboard y saldos además de budgets/deuda.
    // Antes faltaban dashboard.all y accounts.all.
    onSuccess: (updated) => {
      invalidateTransactionSideEffects(queryClient);
      queryClient.setQueryData(queryKeys.transactions.detail(updated.id), updated);
    },
  });
}

export function useDeleteTransaction() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) => transactionsApi.remove(id),
    // Soft-delete (PHASE-10.1) — la fila se va de list/dashboard y
    // aparece en trash. AUDIT-2026-06: borrar también mueve budgets
    // (faltaba) y saldos de cuenta (faltaba); el helper engloba todo.
    onSuccess: () => {
      invalidateTransactionSideEffects(queryClient);
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
    // AUDIT-2026-06: mismo blast radius que delete; añade accounts.all
    // (saldos) vía el helper, que antes no se invalidaba.
    onSuccess: () => {
      invalidateTransactionSideEffects(queryClient);
    },
  });
}

/**
 * PHASE-32 — Reasigna en bloque las tx que matcheen los filtros a otra
 * cuenta (consolidar el mes en la cuenta principal). Cambia balances →
 * invalida también `accounts.balances` y dashboard/debt.
 */
export function useReassignAccount() {
  const queryClient = useQueryClient();
  return useMutation<
    { reassigned_count: number; skipped_other_currency: number },
    Error,
    { targetAccountId: string; filters: TransactionListQuery }
  >({
    mutationFn: ({ targetAccountId, filters }) =>
      transactionsApi.reassignAccount(targetAccountId, filters),
    // AUDIT-2026-06: el helper invalida accounts.all (engloba la
    // balances() que ya se invalidaba aquí) además de tx/dashboard/
    // budgets/deuda.
    onSuccess: () => {
      invalidateTransactionSideEffects(queryClient);
    },
  });
}

/**
 * PHASE-34 — Cambia en bloque la categoría de las tx seleccionadas (por ID).
 * Afecta los desgloses por categoría del dashboard → invalida tx + dashboard
 * (vía el helper). No cambia saldos (es relabel puro), pero el helper
 * compartido cubre todo el blast radius sin coste perceptible.
 */
export function useBulkCategorizeTransactions() {
  const queryClient = useQueryClient();
  return useMutation<
    { updated: number },
    Error,
    { transactionIds: string[]; categoryId: string | null }
  >({
    mutationFn: ({ transactionIds, categoryId }) =>
      transactionsApi.bulkCategorize(transactionIds, categoryId),
    onSuccess: () => {
      invalidateTransactionSideEffects(queryClient);
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
    // Vuelve a list/dashboard, sale de trash. Mismo blast radius que
    // delete pero al revés. AUDIT-2026-06: añade budgets.all y
    // accounts.all (saldos) vía el helper, que antes faltaban.
    onSuccess: () => {
      invalidateTransactionSideEffects(queryClient);
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
    // AUDIT-2026-06: mismo blast radius que restore; el helper añade
    // accounts.all (saldos), que antes no se invalidaba.
    onSuccess: () => {
      invalidateTransactionSideEffects(queryClient);
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
