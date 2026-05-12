import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type {
  Account,
  AccountBalancesResponse,
  AccountCreateRequest,
  AccountUpdateRequest,
  AmortizationSchedule,
  DebtHealthKpis,
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
