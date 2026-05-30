import { useQuery } from '@tanstack/react-query';

import type { DebtCategorySummary, DebtTimeRange } from '@crisol/types';

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
