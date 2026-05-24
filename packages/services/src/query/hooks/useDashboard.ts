import { useQuery } from '@tanstack/react-query';

import type {
  DashboardByCategoryQuery,
  DashboardByMonthQuery,
  DashboardCategoryDetailQuery,
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

/**
 * PHASE-25 — Drill-down de una categoría. Devuelve KPIs (total/count/
 * ticket medio), evolución mensual y top 10 tx. Espera del usuario que
 * pase `currency` (o `target_currency`) — sin filtro el backend usa
 * USD como default y casi nunca es lo que el usuario quiere.
 */
export function useCategoryDetail(
  categoryId: string | undefined,
  query: DashboardCategoryDetailQuery = {},
) {
  return useQuery({
    queryKey: categoryId
      ? queryKeys.dashboard.categoryDetail(
          categoryId,
          query as Record<string, unknown>,
        )
      : queryKeys.dashboard.all,
    queryFn: () => dashboardApi.categoryDetail(categoryId as string, query),
    enabled: !!categoryId,
    staleTime: STALE_TIME,
    placeholderData: (previous) => previous,
  });
}

/**
 * Periodos (año + meses con datos) en los que la categoría dada tiene
 * transacciones activas. Alimenta el TimeSelector del drill-down para
 * que sólo se ofrezcan meses/años con movimientos reales.
 */
export function useCategoryAvailablePeriods(categoryId: string | undefined) {
  return useQuery<{ year: number; months: number[] }[], Error>({
    queryKey: categoryId
      ? queryKeys.dashboard.categoryAvailablePeriods(categoryId)
      : queryKeys.dashboard.all,
    queryFn: () => dashboardApi.categoryAvailablePeriods(categoryId as string),
    enabled: !!categoryId,
    staleTime: STALE_TIME,
  });
}
