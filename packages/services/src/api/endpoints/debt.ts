import type { DebtCategorySummary, DebtTimeRange } from '@crisol/types';

import { apiClient } from '../client';

/**
 * PHASE-30.2 — Endpoints de Capa 1 del módulo deuda. Capa 2
 * (`/accounts/debt-health`, `/accounts/debt-history`) sigue viva en
 * `accountsApi` durante PHASE-30.x.
 */
export const debtApi = {
  async categorySummary(
    range: DebtTimeRange = 'ytd',
  ): Promise<DebtCategorySummary> {
    const response = await apiClient.get<DebtCategorySummary>(
      '/debt/category-summary',
      { params: { range } },
    );
    return response.data;
  },
};
