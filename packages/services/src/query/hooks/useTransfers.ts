import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type {
  AmortizationEffect,
  AmortizationRequest,
  FinancingMatch,
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
 * PHASE-46 — abonos de financiación que encajan con el cuadro de una deuda ya
 * creada y todavía no cuelgan de ella.
 *
 * No hace falta una mutación propia: el enlace lo aplica `useTransferFromDebt`,
 * que es el mismo gesto que ya existía en el detalle de transacción. Aquí sólo
 * se propone.
 */
export function useFinancingMatches() {
  return useQuery<FinancingMatch[], Error>({
    queryKey: queryKeys.transfers.financingMatches(),
    queryFn: () => transfersApi.financingMatches(),
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
 * PHASE-45 — el registro de amortización de una tx, o `null` si no lo tiene.
 *
 * Lo consulta el panel del detalle para saber si ya está registrada (y poder
 * ofrecer deshacerlo) en vez de dejar que el usuario la registre dos veces.
 */
export function useAmortization(transactionId: string) {
  return useQuery<AmortizationEffect | null, Error>({
    queryKey: queryKeys.transfers.amortization(transactionId),
    queryFn: () => transfersApi.amortization(transactionId),
    enabled: Boolean(transactionId),
  });
}

/**
 * PHASE-45 — previsualiza el efecto de una amortización SIN escribir nada.
 *
 * Es el mismo endpoint que la aplica, con `dry_run: true`, para que lo que se
 * enseña y lo que ocurre salgan de la misma cuenta. No invalida nada: no ha
 * cambiado nada.
 */
export function usePreviewAmortization() {
  return useMutation<
    AmortizationEffect,
    Error,
    Omit<AmortizationRequest, 'dry_run'>
  >({
    mutationFn: (payload) => transfersApi.amortize({ ...payload, dry_run: true }),
  });
}

/**
 * PHASE-45 — registra la amortización. Mueve la deuda y (si cuenta como
 * gasto) el cashflow, así que invalida el grupo entero.
 */
export function useAmortize() {
  const queryClient = useQueryClient();
  return useMutation<
    AmortizationEffect,
    Error,
    Omit<AmortizationRequest, 'dry_run'>
  >({
    mutationFn: (payload) => transfersApi.amortize({ ...payload, dry_run: false }),
    onSuccess: () => invalidateAll(queryClient),
  });
}

/** PHASE-45 — deshace el registro: la deuda vuelve a subir. */
export function useUndoAmortization() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (transactionId) => transfersApi.undoAmortization(transactionId),
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
