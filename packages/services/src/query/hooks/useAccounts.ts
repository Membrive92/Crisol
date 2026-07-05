import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type {
  Account,
  AccountBalancesResponse,
  AccountCreateRequest,
  AccountUpdateRequest,
  AmortizationRow,
  AmortizationSchedule,
  InstallmentBulkPayRequest,
  InstallmentBulkPayResponse,
  InstallmentPayRequest,
  InstallmentUpdateRequest,
  PositionHistoryResponse,
} from '@crisol/types';

import { accountsApi } from '../../api/endpoints/accounts';
import { queryKeys } from '../keys';

export function useAccounts(options: { includeArchived?: boolean } = {}) {
  const includeArchived = options.includeArchived ?? false;
  return useQuery({
    queryKey: queryKeys.accounts.list(includeArchived),
    queryFn: () => accountsApi.list({ include_archived: includeArchived }),
    staleTime: 1000 * 60 * 5,
  });
}

export function useAccount(id: string | undefined) {
  return useQuery({
    queryKey: id ? queryKeys.accounts.detail(id) : queryKeys.accounts.all,
    queryFn: () => accountsApi.get(id as string),
    enabled: !!id,
  });
}

export function useCreateAccount() {
  const queryClient = useQueryClient();
  return useMutation<Account, Error, AccountCreateRequest>({
    mutationFn: (data) => accountsApi.create(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all });
      // AUDIT-2026-06: crear una cuenta-pasivo cambia los KPIs/charts de
      // deuda (debt-health, debt-history, category-summary). Sin esto el
      // módulo /debt quedaba stale hasta el staleTime de 60s.
      void queryClient.invalidateQueries({ queryKey: queryKeys.debt.all });
    },
  });
}

export function useUpdateAccount(id: string) {
  const queryClient = useQueryClient();
  return useMutation<Account, Error, AccountUpdateRequest>({
    mutationFn: (data) => accountsApi.update(id, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all });
      // AUDIT-2026-06: editar una cuenta-pasivo (APR, plazo, capital, tipo)
      // recalcula los KPIs de deuda → refrescar el módulo /debt.
      void queryClient.invalidateQueries({ queryKey: queryKeys.debt.all });
    },
  });
}

/**
 * PHASE-34 "Cuadrar saldo": fija el saldo real de una cuenta de activo.
 * `mutate(currentBalance)` con el saldo declarado (string decimal).
 */
export function useReconcileAccount(id: string) {
  const queryClient = useQueryClient();
  return useMutation<Account, Error, string>({
    mutationFn: (currentBalance) => accountsApi.reconcile(id, currentBalance),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.debt.all });
    },
  });
}

export function useDeleteAccount() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) => accountsApi.remove(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all });
      // AUDIT-2026-06: borrar una cuenta-pasivo elimina su deuda de los
      // agregados → refrescar el módulo /debt (si no, KPIs inflados 60s).
      void queryClient.invalidateQueries({ queryKey: queryKeys.debt.all });
    },
  });
}

/**
 * Saldos por cuenta + agregados (patrimonio neto, total pasivos).
 *
 * AUDIT-2026-06 — Acepta `targetCurrency` para convertir todos los
 * saldos a esa divisa (igual que `useDebtHealth`/`useDebtHistory`).
 * Sin ella, la DebtList y la mitad de patrimonio neto del PositionHero
 * se quedaban en divisa nativa mientras el resto de la pantalla estaba
 * convertido, así que dos importes de la misma card no cuadraban.
 */
export function useAccountBalances(options: { targetCurrency?: string } = {}) {
  const targetCurrency = options.targetCurrency;
  return useQuery<AccountBalancesResponse, Error>({
    queryKey: queryKeys.accounts.balances(targetCurrency),
    queryFn: () =>
      accountsApi.balances(
        targetCurrency ? { target_currency: targetCurrency } : {},
      ),
    staleTime: 1000 * 60,
  });
}

/**
 * PHASE-37.1 — Serie temporal de patrimonio (activos / pasivos / neto) + Δ del
 * periodo. Alimenta el sparkline del tile de Patrimonio y la card de evolución.
 */
export function usePositionHistory(monthsBack = 12, monthsForward = 0) {
  return useQuery<PositionHistoryResponse, Error>({
    queryKey: queryKeys.accounts.positionHistory(monthsBack, monthsForward),
    queryFn: () =>
      accountsApi.positionHistory({
        months_back: monthsBack,
        months_forward: monthsForward,
      }),
    staleTime: 1000 * 60,
    placeholderData: (previous) => previous,
  });
}

export function useAmortizationSchedule(id: string | undefined) {
  return useQuery<AmortizationSchedule, Error>({
    queryKey: id
      ? queryKeys.accounts.amortization(id)
      : queryKeys.accounts.all,
    queryFn: () => accountsApi.amortizationSchedule(id as string),
    enabled: !!id,
    staleTime: 1000 * 60 * 5,
  });
}

/**
 * PHASE-24.1: helper común que invalida el cuadro de amortización
 * (accounts.amortization) + balances tras tocar una cuota.
 *
 * AUDIT-2026-05: además invalida `debt.all` — pagar/editar una cuota
 * cambia los KPIs de deuda (debt-health, debt-history, category-summary)
 * y antes quedaban stale hasta el `staleTime` de 60s.
 */
function invalidateAmortization(
  queryClient: ReturnType<typeof useQueryClient>,
) {
  void queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all });
  void queryClient.invalidateQueries({ queryKey: queryKeys.debt.all });
}

/**
 * PHASE-24.3: regenera el cuadro de amortización con los datos
 * actuales de la cuenta. Borra las cuotas existentes (incluido el
 * estado de pago) y vuelve a calcular desde el principal correcto
 * (counterpart tx si la cuenta nació de convert-to-debt, opening
 * balance si no).
 */
export function useRegenerateAmortization() {
  const queryClient = useQueryClient();
  return useMutation<AmortizationSchedule, Error, string>({
    mutationFn: (id) => accountsApi.regenerateAmortization(id),
    onSuccess: () => invalidateAmortization(queryClient),
  });
}

/** PHASE-24.1: PATCH cuota (override puntual de importe/fecha). */
export function useUpdateInstallment() {
  const queryClient = useQueryClient();
  return useMutation<
    AmortizationRow,
    Error,
    { installmentId: string; payload: InstallmentUpdateRequest }
  >({
    mutationFn: ({ installmentId, payload }) =>
      accountsApi.updateInstallment(installmentId, payload),
    onSuccess: () => invalidateAmortization(queryClient),
  });
}

/** PHASE-24.1: marca cuota como pagada (timestamp + tx opcional). */
export function usePayInstallment() {
  const queryClient = useQueryClient();
  return useMutation<
    AmortizationRow,
    Error,
    { installmentId: string; payload?: InstallmentPayRequest }
  >({
    mutationFn: ({ installmentId, payload }) =>
      accountsApi.payInstallment(installmentId, payload ?? {}),
    onSuccess: () => invalidateAmortization(queryClient),
  });
}

/** PHASE-24.1: desmarca cuota → pendiente. */
export function useUnpayInstallment() {
  const queryClient = useQueryClient();
  return useMutation<AmortizationRow, Error, string>({
    mutationFn: (installmentId) => accountsApi.unpayInstallment(installmentId),
    onSuccess: () => invalidateAmortization(queryClient),
  });
}

/**
 * AUDIT-2026-07 (H-05): marca las cuotas que un pago de principal cubre.
 * Lo usa el asistente "Pagar cuota" para que el saldo dirigido por el cuadro
 * (PHASE-36) baje. Invalida amortización + accounts + debt como el resto de
 * mutaciones de cuota.
 */
export function usePayInstallments() {
  const queryClient = useQueryClient();
  return useMutation<
    InstallmentBulkPayResponse,
    Error,
    { accountId: string; payload: InstallmentBulkPayRequest }
  >({
    mutationFn: ({ accountId, payload }) =>
      accountsApi.payInstallments(accountId, payload),
    onSuccess: () => invalidateAmortization(queryClient),
  });
}
