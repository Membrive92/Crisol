import type {
  DashboardByCategoryQuery,
  DashboardByMonthQuery,
  DashboardSummaryQuery,
  DashboardTopExpensesQuery,
  ImportListQuery,
  ReceiptListQuery,
  TransactionListQuery,
} from '@finanzas/types';

/**
 * Query keys centralizados para TanStack Query.
 * Mantener la estructura es clave para invalidaciones precisas.
 */
export const queryKeys = {
  auth: {
    me: ['auth', 'me'] as const,
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
