import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from '../client';
import { dashboardApi } from './dashboard';

describe('dashboardApi', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('summary pasa filtros como params', async () => {
    const spy = vi.spyOn(apiClient, 'get').mockResolvedValue({
      data: {
        income: '100.00',
        expenses: '50.00',
        balance: '50.00',
        transaction_count: 4,
        currency: 'USD',
      },
    });

    await dashboardApi.summary({ currency: 'USD', date_from: '2026-01-01T00:00:00Z' });

    expect(spy).toHaveBeenCalledWith('/dashboard/summary', {
      params: { currency: 'USD', date_from: '2026-01-01T00:00:00Z' },
    });
  });

  it('byCategory pasa kind como param', async () => {
    const spy = vi.spyOn(apiClient, 'get').mockResolvedValue({ data: [] });

    await dashboardApi.byCategory({ currency: 'EUR', kind: 'expense' });

    expect(spy).toHaveBeenCalledWith('/dashboard/by-category', {
      params: { currency: 'EUR', kind: 'expense' },
    });
  });

  it('byMonth pasa el year', async () => {
    const spy = vi.spyOn(apiClient, 'get').mockResolvedValue({ data: [] });

    await dashboardApi.byMonth({ year: 2026, currency: 'USD' });

    expect(spy).toHaveBeenCalledWith('/dashboard/by-month', {
      params: { year: 2026, currency: 'USD' },
    });
  });

  it('topExpenses respeta limit', async () => {
    const spy = vi.spyOn(apiClient, 'get').mockResolvedValue({ data: [] });

    await dashboardApi.topExpenses({ limit: 5 });

    expect(spy).toHaveBeenCalledWith('/dashboard/top-expenses', {
      params: { limit: 5 },
    });
  });
});
