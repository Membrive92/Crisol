import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type {
  DebtCategorySummary,
  DebtHealthKpis,
  DebtHistoryResponse,
  DebtTimeRange,
  DeferredCyclePreview,
  ModuleDashboardSummary,
} from '@crisol/types';

import { debtApi } from '../../api/endpoints/debt';
import { invalidateTransactionSideEffects } from '../invalidate';
import { queryKeys } from '../keys';

/**
 * PHASE-30.2 — Snapshot de Capa 1 del módulo deuda: pagos a deuda
 * agregados, composición por tipo, evolución mensual y tasa de
 * esfuerzo (estricta + ampliada). El rango por defecto es `year`.
 *
 * PHASE-30.6 — Acepta `targetCurrency` para devolver todos los
 * importes convertidos a esa divisa (per-tx, igual que dashboard).
 *
 * PHASE-30.8 — Acepta `anchor` (`YYYY-MM-DD`) para mostrar un período
 * pasado concreto; si se omite, el período en curso.
 *
 * PHASE-41 — `range='custom'` usa `dateFrom`/`dateTo` (rango libre). La query
 * sólo se dispara cuando ambos están presentes en modo custom.
 */
export function useDebtCategorySummary(
  range: DebtTimeRange = 'year',
  options: {
    targetCurrency?: string;
    anchor?: string;
    dateFrom?: string;
    dateTo?: string;
  } = {},
) {
  const { targetCurrency, anchor, dateFrom, dateTo } = options;
  const isCustom = range === 'custom';
  return useQuery<DebtCategorySummary, Error>({
    queryKey: queryKeys.debt.categorySummary(
      range,
      targetCurrency,
      anchor,
      dateFrom,
      dateTo,
    ),
    queryFn: () =>
      debtApi.categorySummary({
        range,
        ...(anchor ? { anchor } : {}),
        ...(isCustom && dateFrom ? { date_from: dateFrom } : {}),
        ...(isCustom && dateTo ? { date_to: dateTo } : {}),
        ...(targetCurrency ? { target_currency: targetCurrency } : {}),
      }),
    // En custom, esperar a tener ambos bounds para no pegar un 422.
    enabled: !isCustom || (Boolean(dateFrom) && Boolean(dateTo)),
    staleTime: 60_000,
  });
}

/**
 * Capa 2 — KPIs de salud financiera basados en pasivos declarados.
 * AUDIT-2026-05: movido desde `useAccounts` a `useDebt` + keys bajo
 * `debt.*` para consolidar el módulo deuda (la URL
 * `/accounts/debt-health` se mantiene estable).
 */
export function useDebtHealth(options: { targetCurrency?: string } = {}) {
  const targetCurrency = options.targetCurrency;
  return useQuery<DebtHealthKpis, Error>({
    queryKey: queryKeys.debt.health(targetCurrency),
    queryFn: () =>
      debtApi.debtHealth(targetCurrency ? { target_currency: targetCurrency } : {}),
    staleTime: 1000 * 60,
  });
}

/**
 * PHASE-43.4 (ADR-0006) — tarjeta del módulo Deuda para el dashboard:
 * deuda viva + esfuerzo + veredicto.
 */
export function useDebtDashboardSummary(
  options: { targetCurrency?: string; dateFrom?: string; dateTo?: string } = {},
) {
  const { targetCurrency, dateFrom, dateTo } = options;
  return useQuery<ModuleDashboardSummary, Error>({
    queryKey: queryKeys.debt.dashboardSummary(targetCurrency, dateFrom, dateTo),
    queryFn: () =>
      debtApi.dashboardSummary({
        ...(targetCurrency ? { target_currency: targetCurrency } : {}),
        ...(dateFrom ? { date_from: dateFrom } : {}),
        ...(dateTo ? { date_to: dateTo } : {}),
      }),
    staleTime: 1000 * 60,
  });
}

/**
 * Capa 2 — evolución histórica + proyección del saldo de deuda.
 * AUDIT-2026-05: movido desde `useAccounts` a `useDebt` + keys bajo
 * `debt.*` (la URL `/accounts/debt-history` se mantiene estable).
 */
export function useDebtHistory(
  options: { monthsBack?: number; monthsAhead?: number; targetCurrency?: string } = {},
) {
  const monthsBack = options.monthsBack ?? 12;
  const monthsAhead = options.monthsAhead ?? 12;
  const targetCurrency = options.targetCurrency;
  return useQuery<DebtHistoryResponse, Error>({
    queryKey: queryKeys.debt.history(monthsBack, monthsAhead, targetCurrency),
    queryFn: () =>
      debtApi.debtHistory({
        months_back: monthsBack,
        months_ahead: monthsAhead,
        ...(targetCurrency ? { target_currency: targetCurrency } : {}),
      }),
    staleTime: 1000 * 60,
  });
}

/**
 * PHASE-47.E — Qué gasto aplazó este recibo financiado. Sólo consulta: el
 * sistema propone con su aritmética a la vista y el usuario declara (ADR-0011).
 */
export function useDeferredCycle(liabilityId: string | null) {
  return useQuery<DeferredCyclePreview, Error>({
    queryKey: queryKeys.debt.deferredCycle(liabilityId ?? 'none'),
    queryFn: () => debtApi.deferredCyclePreview(liabilityId as string),
    enabled: liabilityId !== null,
    staleTime: 1000 * 30,
  });
}

/** Marca las compras del ciclo como aplazadas por este recibo. */
export function useApplyDeferredCycle() {
  const queryClient = useQueryClient();
  return useMutation<DeferredCyclePreview, Error, string>({
    mutationFn: (liabilityId) => debtApi.deferredCycleApply(liabilityId),
    onSuccess: () => invalidateTransactionSideEffects(queryClient),
  });
}

/** Retira la marca: las compras vuelven a contar como salida de caja. */
export function useClearDeferredCycle() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (liabilityId) => debtApi.deferredCycleClear(liabilityId),
    onSuccess: () => invalidateTransactionSideEffects(queryClient),
  });
}
