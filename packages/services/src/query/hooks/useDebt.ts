import { useQuery } from '@tanstack/react-query';

import type { DebtCategorySummary, DebtTimeRange } from '@crisol/types';

import { debtApi } from '../../api/endpoints/debt';
import { queryKeys } from '../keys';

/**
 * PHASE-30.2 — Snapshot de Capa 1 del módulo deuda: pagos a deuda
 * agregados, composición por tipo, evolución mensual y tasa de
 * esfuerzo (estricta + ampliada). El rango por defecto es `ytd`.
 *
 * PHASE-30.6 — Acepta `targetCurrency` para devolver todos los
 * importes convertidos a esa divisa (per-tx, igual que dashboard).
 */
export function useDebtCategorySummary(
  range: DebtTimeRange = 'ytd',
  options: { targetCurrency?: string } = {},
) {
  const targetCurrency = options.targetCurrency;
  return useQuery<DebtCategorySummary, Error>({
    queryKey: queryKeys.debt.categorySummary(range, targetCurrency),
    queryFn: () =>
      debtApi.categorySummary({
        range,
        ...(targetCurrency ? { target_currency: targetCurrency } : {}),
      }),
    staleTime: 60_000,
  });
}
