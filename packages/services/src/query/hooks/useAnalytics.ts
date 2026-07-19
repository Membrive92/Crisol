import { useQuery } from '@tanstack/react-query';

import type { ExpenseStructureQuery, MonthOutlookQuery } from '@crisol/types';

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

/**
 * PHASE-43.2 — Explicabilidad: por qué cada categoría del desglose es Fija o
 * Variable (razón + meses activos/en-banda + overrides). `enabled` para
 * cargarlo sólo cuando se necesita (tooltip/panel), no en cada render.
 */
export function useExpenseStructureExplain(
  query: ExpenseStructureQuery = {},
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: queryKeys.analytics.expenseStructureExplain(query),
    queryFn: () => analyticsApi.expenseStructureExplain(query),
    staleTime: STALE_TIME,
    enabled: options.enabled ?? true,
  });
}

/**
 * PHASE-37.4 — Proyección de fin de mes (cargos comprometidos) + colchón/
 * runway. Sin rango: siempre el mes en curso. Espera `currency` (o
 * `target_currency`) del selector del header.
 */
export function useMonthOutlook(query: MonthOutlookQuery = {}) {
  return useQuery({
    queryKey: queryKeys.analytics.monthOutlook(query),
    queryFn: () => analyticsApi.monthOutlook(query),
    staleTime: STALE_TIME,
    placeholderData: (previous) => previous,
  });
}
