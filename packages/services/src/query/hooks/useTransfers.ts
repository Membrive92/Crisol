import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type {
  MisclassifiedTransfer,
  ReclassifyBulkResponse,
  TransferCandidate,
  TransferFromSourceDebtRequest,
  TransferFromSourceRequest,
  TransferLinkRequest,
  TransferMarkRequest,
  TransferMarkResponse,
  TransferMatchOptions,
  TransferMatchResponse,
  TransferPair,
  TransferSuspect,
} from '@crisol/types';

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
  // AUDIT-2026-07 (M-01): invalidar `accounts.all`, NO `accounts.balances()`.
  // `balances()` resuelve a `['accounts','balances','native']`, que no es
  // prefijo de `['accounts','balances','EUR']` (modo convertAll) → los saldos
  // convertidos y `accounts.list` quedaban stale tras mover una transferencia.
  // `accounts.all` engloba balances(cualquier divisa) + list.
  void queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all });
  // AUDIT-2026-05: un pago a deuda (income transfer a una liability) o
  // un convert-to-debt mueven los KPIs de deuda — refrescarlos también.
  void queryClient.invalidateQueries({ queryKey: queryKeys.debt.all });
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

/**
 * PHASE-23: txs sin pareja cuya descripción contiene "transfer" y
 * todavía no están marcadas como transferencia. El usuario las revisa
 * y decide cuáles marcar.
 */
export function useTransferSuspects() {
  return useQuery<TransferSuspect[], Error>({
    queryKey: queryKeys.transfers.suspects(),
    queryFn: () => transfersApi.suspects(),
    staleTime: 1000 * 60,
  });
}

/**
 * PHASE-23.1: marca una tx como transferencia interna (asigna
 * categoría con is_transfer=true) — la saca del cashflow agregado
 * pero conserva el signo en el saldo de la cuenta.
 */
export function useMarkTransfer() {
  const queryClient = useQueryClient();
  return useMutation<TransferMarkResponse, Error, TransferMarkRequest>({
    mutationFn: (payload) => transfersApi.mark(payload),
    onSuccess: () => {
      invalidateAll(queryClient);
      void queryClient.invalidateQueries({
        queryKey: queryKeys.categories.all,
      });
    },
  });
}

/**
 * PHASE-23.1: convierte una tx existente en una transferencia interna
 * creando la contraparte en la cuenta destino y emparejándolas. Tras
 * el éxito, ambas cuentas reflejan el movimiento en saldo y el par
 * queda excluido del cashflow agregado.
 */
export function useConvertToTransfer() {
  const queryClient = useQueryClient();
  return useMutation<TransferPair, Error, TransferFromSourceRequest>({
    mutationFn: (payload) => transfersApi.fromSource(payload),
    onSuccess: () => invalidateAll(queryClient),
  });
}

/**
 * PHASE-31.2 — tx con categoría is_transfer y dirección dudosa.
 * Refresca con cualquier cambio en transfers o transactions.
 */
export function useMisclassifiedTransfers() {
  return useQuery<MisclassifiedTransfer[], Error>({
    queryKey: queryKeys.transfers.misclassified(),
    queryFn: () => transfersApi.misclassified(),
    staleTime: 1000 * 30,
  });
}

/**
 * PHASE-31.2 — recategorización en bloque de transferencias mal
 * direccionadas. Tras el éxito invalida todo el grupo de transfers
 * + transactions + balances + dashboard (los saldos cambian).
 */
export function useReclassifyBulk() {
  const queryClient = useQueryClient();
  return useMutation<
    ReclassifyBulkResponse,
    Error,
    { transaction_ids: string[]; target_category_id?: string }
  >({
    mutationFn: (payload) => transfersApi.reclassifyBulk(payload),
    onSuccess: () => invalidateAll(queryClient),
  });
}

/**
 * PHASE-24: convierte una tx en operación financiada. La contraparte
 * va a una cuenta liability (existente o creada al vuelo). Tras el
 * éxito invalidamos también accounts.list (puede haberse creado una
 * nueva cuenta) y debt KPIs.
 */
export function useConvertToDebt() {
  const queryClient = useQueryClient();
  return useMutation<TransferPair, Error, TransferFromSourceDebtRequest>({
    mutationFn: (payload) => transfersApi.fromSourceDebt(payload),
    onSuccess: () => {
      invalidateAll(queryClient);
      // Nueva liability + cuadro de amortización pueden ser nuevos.
      void queryClient.invalidateQueries({
        queryKey: queryKeys.accounts.all,
      });
    },
  });
}
