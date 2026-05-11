import { useQuery } from '@tanstack/react-query';

import type {
  DashboardByCategoryQuery,
  DashboardByMonthQuery,
  DashboardSummaryQuery,
  DashboardTopExpensesQuery,
} from '@crisol/types';

import { dashboardApi } from '../../api/endpoints/dashboard';
import { queryKeys } from '../keys';

const STALE_TIME = 60_000;
// Las monedas del usuario cambian poco; cache larga para que el filtro
// del dashboard no parpadee al navegar entre páginas.
const CURRENCIES_STALE_TIME = 5 * 60_000;

export function useUserCurrencies() {
  return useQuery({
    queryKey: queryKeys.dashboard.currencies(),
    queryFn: () => dashboardApi.currencies(),
    staleTime: CURRENCIES_STALE_TIME,
    placeholderData: (previous) => previous,
  });
}

export function useDashboardSummary(query: DashboardSummaryQuery = {}) {
  return useQuery({
    queryKey: queryKeys.dashboard.summary(query),
    queryFn: () => dashboardApi.summary(query),
    staleTime: STALE_TIME,
    placeholderData: (previous) => previous,
  });
}

export function useDashboardByCategory(query: DashboardByCategoryQuery = {}) {
  return useQuery({
    queryKey: queryKeys.dashboard.byCategory(query),
    queryFn: () => dashboardApi.byCategory(query),
    staleTime: STALE_TIME,
    placeholderData: (previous) => previous,
  });
}

export function useDashboardByMonth(query: DashboardByMonthQuery = {}) {
  return useQuery({
    queryKey: queryKeys.dashboard.byMonth(query),
    queryFn: () => dashboardApi.byMonth(query),
    staleTime: STALE_TIME,
    placeholderData: (previous) => previous,
  });
}

export function useDashboardTopExpenses(query: DashboardTopExpensesQuery = {}) {
  return useQuery({
    queryKey: queryKeys.dashboard.topExpenses(query),
    queryFn: () => dashboardApi.topExpenses(query),
    staleTime: STALE_TIME,
    placeholderData: (previous) => previous,
  });
}
