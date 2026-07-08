import { useQuery } from '@tanstack/react-query';

import type { ExpenseStructureQuery } from '@crisol/types';

import { analyticsApi } from '../../api/endpoints/analytics';
import { queryKeys } from '../keys';

const STALE_TIME = 60_000;

/**
 * PHASE-37.3 — Gasto estructural vs puntual + tasa de ahorro dual para el
 * rango. Espera del usuario que pase `currency` (o `target_currency`); sin
 * filtro el backend usa USD por defecto. `placeholderData` mantiene las
 * cifras del período anterior mientras refetchea (sin parpadeo al navegar).
 */
export function useExpenseStructure(query: ExpenseStructureQuery = {}) {
  return useQuery({
    queryKey: queryKeys.analytics.expenseStructure(query),
    queryFn: () => analyticsApi.expenseStructure(query),
    staleTime: STALE_TIME,
    placeholderData: (previous) => previous,
  });
}
