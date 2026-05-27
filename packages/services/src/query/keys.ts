import type {
  DashboardByCategoryQuery,
  DashboardByMonthQuery,
  DashboardSummaryQuery,
  DashboardTopExpensesQuery,
  ImportListQuery,
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
    balances: () => [...queryKeys.accounts.all, 'balances'] as const,
    debtHealth: (targetCurrency?: string) =>
      [
        ...queryKeys.accounts.all,
        'debt-health',
        targetCurrency ?? 'native',
      ] as const,
    debtHistory: (
      monthsBack = 12,
      monthsAhead = 12,
      targetCurrency?: string,
    ) =>
      [
        ...queryKeys.accounts.all,
        'debt-history',
        monthsBack,
        monthsAhead,
        targetCurrency ?? 'native',
      ] as const,
    amortization: (id: string) =>
      [...queryKeys.accounts.all, 'amortization', id] as const,
  },
  debt: {
    all: ['debt'] as const,
    categorySummary: (
      range: 'ytd' | '12m' | 'month' = 'ytd',
      targetCurrency?: string,
    ) =>
      [
        ...queryKeys.debt.all,
        'category-summary',
        range,
        targetCurrency ?? 'native',
      ] as const,
  },
  transfers: {
    all: ['transfers'] as const,
    list: () => [...queryKeys.transfers.all, 'list'] as const,
    candidates: (windowDays = 3) =>
      [...queryKeys.transfers.all, 'candidates', windowDays] as const,
    suspects: () => [...queryKeys.transfers.all, 'suspects'] as const,
    misclassified: () => [...queryKeys.transfers.all, 'misclassified'] as const,
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
    availablePeriods: () => [...queryKeys.transactions.all, 'available-periods'] as const,
    uncategorizedSummary: () =>
      [...queryKeys.transactions.all, 'uncategorized-summary'] as const,
  },
  dashboard: {
    all: ['dashboard'] as const,
    summary: (query: DashboardSummaryQuery = {}) =>
      [...queryKeys.dashboard.all, 'summary', normalizeQuery(query)] as const,
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
