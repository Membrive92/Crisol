import type {
  DebtCategorySummary,
  DebtHealthKpis,
  DebtHistoryResponse,
  DebtTimeRange,
} from '@crisol/types';

import { apiClient } from '../client';

export interface CategorySummaryQuery {
  range?: DebtTimeRange;
  /**
   * PHASE-30.8 — Cualquier día (`YYYY-MM-DD`) dentro del período a
   * mostrar. `range` fija el tipo (mes/año); `anchor` decide cuál. Si se
   * omite, el período en curso. Se ignora con `range='custom'`.
   */
  anchor?: string;
  /** PHASE-41 — Inicio del rango libre (`YYYY-MM-DD`), obligatorio con `range='custom'`. */
  date_from?: string;
  /** PHASE-41 — Fin del rango libre (`YYYY-MM-DD`), obligatorio con `range='custom'`. */
  date_to?: string;
  /** PHASE-30.6 — Convierte todos los importes a esta divisa (per-tx). */
  target_currency?: string;
}

export interface DebtHistoryQuery {
  /** Meses cerrados hacia atrás (1-36). Default 12. */
  months_back?: number;
  /** Meses proyectados hacia adelante (0-36, 0 desactiva). Default 12. */
  months_ahead?: number;
  /** PHASE-30.6 — Convierte saldos y flujo histórico a esta divisa. */
  target_currency?: string;
}

export interface DebtHealthQuery {
  /** PHASE-30.6 — Convierte saldos y KPIs a esta divisa. */
  target_currency?: string;
}

/**
 * Endpoints del módulo deuda. AUDIT-2026-05 — Capa 1
 * (`/debt/category-summary`) + Capa 2 (`/accounts/debt-health`,
 * `/accounts/debt-history`) consolidadas aquí; antes la Capa 2 vivía en
 * `accountsApi`. Las URLs `/accounts/debt-*` se mantienen estables (su
 * migración a `/debt/*` es un cambio de contrato versionado futuro).
 */
export const debtApi = {
  async categorySummary(
    query: CategorySummaryQuery = {},
  ): Promise<DebtCategorySummary> {
    const params: Record<string, string> = {
      range: query.range ?? 'year',
    };
    if (query.anchor) {
      params['anchor'] = query.anchor;
    }
    if (query.date_from) {
      params['date_from'] = query.date_from;
    }
    if (query.date_to) {
      params['date_to'] = query.date_to;
    }
    if (query.target_currency) {
      params['target_currency'] = query.target_currency;
    }
    const response = await apiClient.get<DebtCategorySummary>(
      '/debt/category-summary',
      { params },
    );
    return response.data;
  },

  async debtHealth(query: DebtHealthQuery = {}): Promise<DebtHealthKpis> {
    const params: Record<string, string> = {};
    if (query.target_currency) params['target_currency'] = query.target_currency;
    const response = await apiClient.get<DebtHealthKpis>('/accounts/debt-health', {
      params,
    });
    return response.data;
  },

  async debtHistory(query: DebtHistoryQuery = {}): Promise<DebtHistoryResponse> {
    const params: Record<string, string | number> = {};
    if (query.months_back !== undefined) params['months_back'] = query.months_back;
    if (query.months_ahead !== undefined) params['months_ahead'] = query.months_ahead;
    if (query.target_currency) params['target_currency'] = query.target_currency;
    const response = await apiClient.get<DebtHistoryResponse>(
      '/accounts/debt-history',
      { params },
    );
    return response.data;
  },
};
