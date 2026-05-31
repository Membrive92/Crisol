import { useQuery } from '@tanstack/react-query';

import type {
  DebtCategorySummary,
  DebtHealthKpis,
  DebtHistoryResponse,
  DebtTimeRange,
} from '@crisol/types';

import { debtApi } from '../../api/endpoints/debt';
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
 */
export function useDebtCategorySummary(
  range: DebtTimeRange = 'year',
  options: { targetCurrency?: string; anchor?: string } = {},
) {
  const { targetCurrency, anchor } = options;
  return useQuery<DebtCategorySummary, Error>({
    queryKey: queryKeys.debt.categorySummary(range, targetCurrency, anchor),
    queryFn: () =>
      debtApi.categorySummary({
        range,
        ...(anchor ? { anchor } : {}),
        ...(targetCurrency ? { target_currency: targetCurrency } : {}),
      }),
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
