import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from '../client';
import { debtApi } from './debt';

describe('debtApi', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('categorySummary pega a /debt/category-summary con range por defecto', async () => {
    const spy = vi.spyOn(apiClient, 'get').mockResolvedValue({ data: {} });
    await debtApi.categorySummary();
    expect(spy).toHaveBeenCalledWith('/debt/category-summary', {
      params: { range: 'year' },
    });
  });

  it('categorySummary propaga anchor + target_currency', async () => {
    const spy = vi.spyOn(apiClient, 'get').mockResolvedValue({ data: {} });
    await debtApi.categorySummary({
      range: 'month',
      anchor: '2024-04-01',
      target_currency: 'USD',
    });
    expect(spy).toHaveBeenCalledWith('/debt/category-summary', {
      params: { range: 'month', anchor: '2024-04-01', target_currency: 'USD' },
    });
  });

  // AUDIT-2026-05: debtHealth/debtHistory se movieron de accountsApi a
  // debtApi, pero las URLs /accounts/debt-* se mantienen estables (no es
  // un cambio de contrato HTTP).
  it('debtHealth conserva la URL /accounts/debt-health', async () => {
    const spy = vi.spyOn(apiClient, 'get').mockResolvedValue({ data: {} });
    await debtApi.debtHealth({ target_currency: 'USD' });
    expect(spy).toHaveBeenCalledWith('/accounts/debt-health', {
      params: { target_currency: 'USD' },
    });
  });

  it('debtHistory conserva la URL /accounts/debt-history y pasa los meses', async () => {
    const spy = vi.spyOn(apiClient, 'get').mockResolvedValue({ data: {} });
    await debtApi.debtHistory({ months_back: 6, months_ahead: 0 });
    expect(spy).toHaveBeenCalledWith('/accounts/debt-history', {
      params: { months_back: 6, months_ahead: 0 },
    });
  });
});
