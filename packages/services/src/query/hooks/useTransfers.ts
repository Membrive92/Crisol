import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type {
  MisclassifiedTransfer,
  ReclassifyBulkResponse,
  TransferFromSourceDebtRequest,
  TransferFromSourceRequest,
  TransferLinkRequest,
  TransferPair,
} from '@crisol/types';

import { transfersApi } from '../../api/endpoints/transfers';
import { queryKeys } from '../keys';

function invalidateAll(queryClient: ReturnType<typeof useQueryClient>) {
  // link/unlink/from-source afectan a transferencias y a todos los
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
 * Enlaza dos transacciones explícitamente como par de transferencia.
 * Load-bearing: lo usa el asistente de pago de deuda para crear el par
 * principal (ADR-0005 T3 — `convert_to_debt` aún depende del par).
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
