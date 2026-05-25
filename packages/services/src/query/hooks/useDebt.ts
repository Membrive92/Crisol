import { useQuery } from '@tanstack/react-query';

import type { DebtCategorySummary, DebtTimeRange } from '@crisol/types';

import { debtApi } from '../../api/endpoints/debt';
import { queryKeys } from '../keys';

/**
 * PHASE-30.2 — Snapshot de Capa 1 del módulo deuda: pagos a deuda
 * agregados, composición por tipo, evolución mensual y tasa de
 * esfuerzo (estricta + ampliada). El rango por defecto es `ytd`.
 */
export function useDebtCategorySummary(range: DebtTimeRange = 'ytd') {
  return useQuery<DebtCategorySummary, Error>({
    queryKey: queryKeys.debt.categorySummary(range),
    queryFn: () => debtApi.categorySummary(range),
    staleTime: 60_000,
  });
}
