import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type {
  Account,
  AccountBalancesResponse,
  AccountCreateRequest,
  AccountUpdateRequest,
  AmortizationRow,
  AmortizationSchedule,
  DebtHealthKpis,
  DebtHistoryResponse,
  InstallmentPayRequest,
  InstallmentUpdateRequest,
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
    },
  });
}

export function useUpdateAccount(id: string) {
  const queryClient = useQueryClient();
  return useMutation<Account, Error, AccountUpdateRequest>({
    mutationFn: (data) => accountsApi.update(id, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all });
    },
  });
}

export function useDeleteAccount() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) => accountsApi.remove(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all });
    },
  });
}

export function useAccountBalances() {
  return useQuery<AccountBalancesResponse, Error>({
    queryKey: queryKeys.accounts.balances(),
    queryFn: () => accountsApi.balances(),
    staleTime: 1000 * 60,
  });
}

export function useDebtHealth() {
  return useQuery<DebtHealthKpis, Error>({
    queryKey: queryKeys.accounts.debtHealth(),
    queryFn: () => accountsApi.debtHealth(),
    staleTime: 1000 * 60,
  });
}

export function useDebtHistory(
  options: { monthsBack?: number; monthsAhead?: number } = {},
) {
  const monthsBack = options.monthsBack ?? 12;
  const monthsAhead = options.monthsAhead ?? 12;
  return useQuery<DebtHistoryResponse, Error>({
    queryKey: queryKeys.accounts.debtHistory(monthsBack, monthsAhead),
    queryFn: () =>
      accountsApi.debtHistory({
        months_back: monthsBack,
        months_ahead: monthsAhead,
      }),
    staleTime: 1000 * 60,
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
 * (accounts.amortization), balances y debt-health tras tocar una cuota.
 */
function invalidateAmortization(
  queryClient: ReturnType<typeof useQueryClient>,
) {
  void queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all });
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
