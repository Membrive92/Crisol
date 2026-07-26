import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from '../client';
import { investmentApi } from './investment';

describe('investmentApi', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('searchSecurities pega a /investment/securities/search', async () => {
    const spy = vi
      .spyOn(apiClient, 'get')
      .mockResolvedValue({ data: { results: [], external_search_available: false } });
    await investmentApi.searchSecurities('mcd');
    expect(spy).toHaveBeenCalledWith('/investment/securities/search', {
      params: { q: 'mcd', limit: 20 },
    });
  });

  it('resolveSecurity postea ticker + exchange', async () => {
    const spy = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: {} });
    await investmentApi.resolveSecurity({ ticker: 'MCD', exchange: 'NYSE' });
    expect(spy).toHaveBeenCalledWith('/investment/securities/resolve', {
      ticker: 'MCD',
      exchange: 'NYSE',
    });
  });

  it('ingest pega al endpoint del security', async () => {
    const spy = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: {} });
    await investmentApi.ingest('sec-1', { filings_back: 5 });
    expect(spy).toHaveBeenCalledWith('/investment/fundamentals/sec-1/ingest', {
      filings_back: 5,
    });
  });

  it('listStatements desenvuelve items', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValue({ data: { items: [{ id: 'x' }] } });
    const items = await investmentApi.listStatements('sec-1');
    expect(items).toEqual([{ id: 'x' }]);
  });

  it('runAnalysis postea al run del security', async () => {
    const spy = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: {} });
    await investmentApi.runAnalysis('sec-1', {});
    expect(spy).toHaveBeenCalledWith('/investment/analysis/sec-1/run', {});
  });

  it('getPortfolioSummary pega a /investment/portfolio/summary', async () => {
    const spy = vi.spyOn(apiClient, 'get').mockResolvedValue({ data: {} });
    await investmentApi.getPortfolioSummary();
    expect(spy).toHaveBeenCalledWith('/investment/portfolio/summary');
  });

  it('refreshPricing postea security_ids', async () => {
    const spy = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: { refreshed: 0 } });
    await investmentApi.refreshPricing({ security_ids: ['a'] });
    expect(spy).toHaveBeenCalledWith('/investment/pricing/refresh', {
      security_ids: ['a'],
    });
  });
});
