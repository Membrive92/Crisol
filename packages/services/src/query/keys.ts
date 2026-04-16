import type { TransactionListQuery } from '@finanzas/types';

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
      [...queryKeys.transactions.all, 'list', normalizeListQuery(query)] as const,
    detail: (id: string) => [...queryKeys.transactions.all, 'detail', id] as const,
  },
} as const;

/**
 * Ordena las claves del query para que objetos equivalentes generen
 * la misma cache key independientemente del orden de propiedades.
 */
function normalizeListQuery(query: TransactionListQuery): Record<string, unknown> {
  const entries = Object.entries(query).filter(([, v]) => v !== undefined && v !== '');
  entries.sort(([a], [b]) => a.localeCompare(b));
  return Object.fromEntries(entries);
}
