import type {
  DashboardByCategoryQuery,
  DashboardByMonthQuery,
  DashboardSummaryQuery,
  DashboardTopExpensesQuery,
  ExpenseStructureQuery,
  ImportListQuery,
  MonthOutlookQuery,
  ReceiptListQuery,
  TransactionListQuery,
} from '@crisol/types';

/**
 * Query keys centralizados para TanStack Query.
 * Mantener la estructura es clave para invalidaciones precisas.
 */
export const queryKeys = {
  auth: {
    me: ['auth', 'me'] as const,
  },
  accounts: {
    all: ['accounts'] as const,
    list: (includeArchived = false) =>
      [...queryKeys.accounts.all, 'list', includeArchived] as const,
    detail: (id: string) => [...queryKeys.accounts.all, 'detail', id] as const,
    balances: (targetCurrency?: string) =>
      [...queryKeys.accounts.all, 'balances', targetCurrency ?? 'native'] as const,
    positionHistory: (monthsBack = 12, monthsForward = 0) =>
      [...queryKeys.accounts.all, 'position-history', monthsBack, monthsForward] as const,
    positionAsOf: (dateFrom: string, dateTo: string) =>
      [...queryKeys.accounts.all, 'position-as-of', dateFrom, dateTo] as const,
    amortization: (id: string) =>
      [...queryKeys.accounts.all, 'amortization', id] as const,
    // PHASE-47.A — propuesta de "desde qué cuenta se cobra este pasivo".
    // Cuelga de `accounts.all` porque la evidencia son enlaces de cargos:
    // cualquier mutación de cuentas o de vínculos la puede mover.
    settlementCandidate: (id: string) =>
      [...queryKeys.accounts.all, 'settlement-candidate', id] as const,
  },
  // AUDIT-2026-05: debt-health/debt-history viven bajo `debt.*` (antes
  // bajo `accounts.*`). Así `debt.all` es el único objetivo de
  // invalidación de todo lo de deuda (Capa 1 + Capa 2), y las
  // mutaciones que mueven deuda invalidan un solo namespace.
  debt: {
    all: ['debt'] as const,
    categorySummary: (
      range: 'month' | 'year' | 'custom' = 'year',
      targetCurrency?: string,
      // PHASE-30.8 — `anchor` (YYYY-MM-DD) del período; `'current'`
      // como sentinel cuando se omite, para no invalidar las keys
      // existentes que no navegan en el tiempo.
      anchor?: string,
      // PHASE-41 — bounds del rango libre (`range='custom'`).
      dateFrom?: string,
      dateTo?: string,
    ) =>
      [
        ...queryKeys.debt.all,
        'category-summary',
        range,
        targetCurrency ?? 'native',
        anchor ?? 'current',
        dateFrom ?? 'none',
        dateTo ?? 'none',
      ] as const,
    // PHASE-47.E — el ciclo aplazado de un pasivo concreto.
    deferredCycle: (liabilityId: string) =>
      [...queryKeys.debt.all, 'deferred-cycle', liabilityId] as const,
    health: (targetCurrency?: string) =>
      [...queryKeys.debt.all, 'health', targetCurrency ?? 'native'] as const,
    dashboardSummary: (targetCurrency?: string, dateFrom?: string, dateTo?: string) =>
      [
        ...queryKeys.debt.all,
        'dashboard-summary',
        targetCurrency ?? 'native',
        dateFrom ?? 'none',
        dateTo ?? 'none',
      ] as const,
    history: (monthsBack = 12, monthsAhead = 12, targetCurrency?: string) =>
      [
        ...queryKeys.debt.all,
        'history',
        monthsBack,
        monthsAhead,
        targetCurrency ?? 'native',
      ] as const,
  },
  transfers: {
    all: ['transfers'] as const,
    // PHASE-41 (ADR-0005) — retiradas list/candidates/suspects con el
    // emparejado heurístico. `all` sigue usándose para invalidar tras
    // link/unlink/convert; `misclassified` alimenta la data-hygiene.
    misclassified: () => [...queryKeys.transfers.all, 'misclassified'] as const,
    // PHASE-46 — abonos de financiación que encajan con el cuadro de una deuda.
    financingMatches: () =>
      [...queryKeys.transfers.all, 'financing-matches'] as const,
    // PHASE-45 — registro de amortización de una tx concreta (o su ausencia).
    amortization: (transactionId: string) =>
      [...queryKeys.transfers.all, 'amortization', transactionId] as const,
  },
  categories: {
    all: ['categories'] as const,
    list: () => [...queryKeys.categories.all, 'list'] as const,
    detail: (id: string) => [...queryKeys.categories.all, 'detail', id] as const,
  },
  transactions: {
    all: ['transactions'] as const,
    list: (query: TransactionListQuery = {}) =>
      [...queryKeys.transactions.all, 'list', normalizeQuery(query)] as const,
    detail: (id: string) => [...queryKeys.transactions.all, 'detail', id] as const,
    trash: (query: { limit?: number; offset?: number } = {}) =>
      [...queryKeys.transactions.all, 'trash', normalizeQuery(query)] as const,
    availablePeriods: (cycle = false) =>
      [...queryKeys.transactions.all, 'available-periods', { cycle }] as const,
    uncategorizedSummary: () =>
      [...queryKeys.transactions.all, 'uncategorized-summary'] as const,
  },
  dashboard: {
    all: ['dashboard'] as const,
    summary: (query: DashboardSummaryQuery = {}) =>
      [...queryKeys.dashboard.all, 'summary', normalizeQuery(query)] as const,
    moduleSummary: (
      query: {
        currency?: string;
        target_currency?: string;
        date_from?: string;
        date_to?: string;
      } = {},
    ) => [...queryKeys.dashboard.all, 'module-summary', normalizeQuery(query)] as const,
    byCategory: (query: DashboardByCategoryQuery = {}) =>
      [...queryKeys.dashboard.all, 'by-category', normalizeQuery(query)] as const,
    byMonth: (query: DashboardByMonthQuery = {}) =>
      [...queryKeys.dashboard.all, 'by-month', normalizeQuery(query)] as const,
    topExpenses: (query: DashboardTopExpensesQuery = {}) =>
      [...queryKeys.dashboard.all, 'top-expenses', normalizeQuery(query)] as const,
    currencies: () => [...queryKeys.dashboard.all, 'currencies'] as const,
    categoryDetail: (categoryId: string, query: Record<string, unknown> = {}) =>
      [
        ...queryKeys.dashboard.all,
        'category-detail',
        categoryId,
        normalizeQuery(query),
      ] as const,
    categoryAvailablePeriods: (categoryId: string) =>
      [
        ...queryKeys.dashboard.all,
        'category-available-periods',
        categoryId,
      ] as const,
  },
  analytics: {
    all: ['analytics'] as const,
    expenseStructure: (query: ExpenseStructureQuery = {}) =>
      [...queryKeys.analytics.all, 'expense-structure', normalizeQuery(query)] as const,
    expenseStructureExplain: (query: ExpenseStructureQuery = {}) =>
      [...queryKeys.analytics.all, 'expense-structure-explain', normalizeQuery(query)] as const,
    monthOutlook: (query: MonthOutlookQuery = {}) =>
      [...queryKeys.analytics.all, 'month-outlook', normalizeQuery(query)] as const,
  },
  imports: {
    all: ['imports'] as const,
    list: (query: ImportListQuery = {}) =>
      [...queryKeys.imports.all, 'list', normalizeQuery(query)] as const,
    detail: (id: string) => [...queryKeys.imports.all, 'detail', id] as const,
  },
  receipts: {
    all: ['receipts'] as const,
    list: (query: ReceiptListQuery = {}) =>
      [...queryKeys.receipts.all, 'list', normalizeQuery(query)] as const,
    detail: (id: string) => [...queryKeys.receipts.all, 'detail', id] as const,
  },
  currency: {
    all: ['currency'] as const,
    rates: (date: string | undefined) =>
      [...queryKeys.currency.all, 'rates', date ?? 'today'] as const,
  },
  budgets: {
    all: ['budgets'] as const,
    list: () => [...queryKeys.budgets.all, 'list'] as const,
    detail: (id: string) => [...queryKeys.budgets.all, 'detail', id] as const,
    status: () => [...queryKeys.budgets.all, 'status'] as const,
  },
  fixedExpenses: {
    all: ['fixedExpenses'] as const,
    list: (status?: string) =>
      [...queryKeys.fixedExpenses.all, 'list', status ?? 'any'] as const,
    detail: (id: string) =>
      [...queryKeys.fixedExpenses.all, 'detail', id] as const,
  },
  bankMappings: {
    all: ['bankMappings'] as const,
  },
  categoryRules: {
    all: ['categoryRules'] as const,
  },
  // PHASE-44.7 — todo lo del módulo Inversión desciende de `investment.all`,
  // así una sola invalidación limpia el módulo entero.
  investment: {
    all: ['investment'] as const,
    // La búsqueda cuelga de una raíz HERMANA, no de `investment.all`
    // (PHASE-44.8 E1). Todas las mutaciones del módulo invalidan `investment.all`
    // para refrescar cartera y análisis; con la búsqueda dentro, elegir un valor
    // invalidaba la propia lista que lo acababa de ofrecer y la relanzaba entera.
    search: (q: string) => ['investment-search', q] as const,
    security: (id: string) => [...queryKeys.investment.all, 'security', id] as const,
    statements: (id: string, view: string) =>
      [...queryKeys.investment.all, 'statements', id, view] as const,
    restatements: (id: string) =>
      [...queryKeys.investment.all, 'restatements', id] as const,
    job: (id: string) => [...queryKeys.investment.all, 'job', id] as const,
    runs: (securityId: string) => [...queryKeys.investment.all, 'runs', securityId] as const,
    run: (id: string) => [...queryKeys.investment.all, 'run', id] as const,
    /** La comparación de dos análisis (PHASE-44.24.F). Bajo `investment.all`
     *  para que `useRunAnalysis` la invalide al reejecutar: si no, el
     *  comparador seguiría enseñando el diff de antes del rerun. */
    compare: (securityId: string, base: string | null, target: string | null) =>
      [...queryKeys.investment.all, 'compare', securityId, base ?? '', target ?? ''] as const,
    latestRun: (securityId: string) =>
      [...queryKeys.investment.all, 'run', 'latest', securityId] as const,
    // El precio entra en la key: cambiar el precio simulado es OTRA consulta,
    // no la misma cacheada. Sin él, teclear un precio distinto devolvería los
    // múltiplos del anterior.
    valuation: (securityId: string, price?: string) =>
      [...queryKeys.investment.all, 'valuation', securityId, price ?? 'market'] as const,
    // Los dos catálogos cuelgan de una raíz HERMANA por el mismo motivo que la
    // búsqueda: son ESTÁTICOS (definición del engine, no datos del usuario), así
    // que una invalidación del módulo no debe volver a pedirlos.
    metricCatalog: () => ['investment-catalog', 'metrics'] as const,
    canonicalItems: () => ['investment-catalog', 'items'] as const,
    helpCatalog: () => ['investment-catalog', 'help'] as const,
    lots: (securityId?: string) =>
      [...queryKeys.investment.all, 'lots', securityId ?? 'all'] as const,
    sales: () => [...queryKeys.investment.all, 'sales'] as const,
    dividends: () => [...queryKeys.investment.all, 'dividends'] as const,
    corporateActions: () => [...queryKeys.investment.all, 'corporate-actions'] as const,
    positions: () => [...queryKeys.investment.all, 'positions'] as const,
    summary: () => [...queryKeys.investment.all, 'summary'] as const,
  },
} as const;

/**
 * Ordena las claves del query para que objetos equivalentes generen
 * la misma cache key independientemente del orden de propiedades.
 */
function normalizeQuery<T extends object>(query: T): Record<string, unknown> {
  const entries = Object.entries(query).filter(([, v]) => v !== undefined && v !== '');
  entries.sort(([a], [b]) => a.localeCompare(b));
  return Object.fromEntries(entries);
}
