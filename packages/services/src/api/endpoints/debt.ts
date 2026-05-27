import type { DebtCategorySummary, DebtTimeRange } from '@crisol/types';

import { apiClient } from '../client';

export interface CategorySummaryQuery {
  range?: DebtTimeRange;
  /** PHASE-30.6 — Convierte todos los importes a esta divisa (per-tx). */
  target_currency?: string;
}

/**
 * PHASE-30.2 — Endpoints de Capa 1 del módulo deuda. Capa 2
 * (`/accounts/debt-health`, `/accounts/debt-history`) sigue viva en
 * `accountsApi` durante PHASE-30.x.
 */
export const debtApi = {
  async categorySummary(
    query: CategorySummaryQuery = {},
  ): Promise<DebtCategorySummary> {
    const params: Record<string, string> = {
      range: query.range ?? 'ytd',
    };
    if (query.target_currency) {
      params['target_currency'] = query.target_currency;
    }
    const response = await apiClient.get<DebtCategorySummary>(
      '/debt/category-summary',
      { params },
    );
    return response.data;
  },
};
