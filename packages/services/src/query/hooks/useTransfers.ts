import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type {
  TransferCandidate,
  TransferLinkRequest,
  TransferMatchOptions,
  TransferMatchResponse,
  TransferPair,
} from '@finanzas/types';

import { transfersApi } from '../../api/endpoints/transfers';
import { queryKeys } from '../keys';

/**
 * Pares emparejados activos del usuario.
 */
export function useTransfers() {
  return useQuery<TransferPair[], Error>({
    queryKey: queryKeys.transfers.list(),
    queryFn: () => transfersApi.list(),
    staleTime: 1000 * 60,
  });
}

/**
 * Sugerencias del matcher heurístico — sin escribir nada en BD.
 */
export function useTransferCandidates(windowDays = 3) {
  return useQuery<TransferCandidate[], Error>({
    queryKey: queryKeys.transfers.candidates(windowDays),
    queryFn: () => transfersApi.candidates(windowDays),
    staleTime: 1000 * 60,
  });
}

function invalidateAll(queryClient: ReturnType<typeof useQueryClient>) {
  // El match/link/unlink afecta a transferencias y a todos los
  // agregados que excluyen pares (dashboard, budgets) + a la lista
  // de transactions (transfer_pair_id cambia) + a balances.
  void queryClient.invalidateQueries({ queryKey: queryKeys.transfers.all });
  void queryClient.invalidateQueries({ queryKey: queryKeys.transactions.all });
  void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
  void queryClient.invalidateQueries({ queryKey: queryKeys.budgets.all });
  void queryClient.invalidateQueries({ queryKey: queryKeys.accounts.balances() });
}

/**
 * Ejecuta el matcher: enlaza los pares no ambiguos y devuelve los
 * ambiguos para que el usuario los confirme manualmente.
 */
export function useMatchTransfers() {
  const queryClient = useQueryClient();
  return useMutation<TransferMatchResponse, Error, TransferMatchOptions | void>({
    mutationFn: (options) => transfersApi.match(options ?? {}),
    onSuccess: () => invalidateAll(queryClient),
  });
}

/**
 * Enlaza dos transacciones explícitamente como par de transferencia.
 */
export function useLinkTransfer() {
  const queryClient = useQueryClient();
  return useMutation<TransferPair, Error, TransferLinkRequest>({
    mutationFn: (payload) => transfersApi.link(payload),
    onSuccess: () => invalidateAll(queryClient),
  });
}

/**
 * Deshace el par del que `transactionId` forma parte.
 */
export function useUnlinkTransfer() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (transactionId) => transfersApi.unlink(transactionId),
    onSuccess: () => invalidateAll(queryClient),
  });
}
