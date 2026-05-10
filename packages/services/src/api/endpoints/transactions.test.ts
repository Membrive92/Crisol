import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from '../client';
import { transactionsApi } from './transactions';

describe('transactionsApi', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('list pasa los filtros como params', async () => {
    const spy = vi
      .spyOn(apiClient, 'get')
      .mockResolvedValue({ data: { items: [], total: 0, limit: 10, offset: 0 } });

    await transactionsApi.list({ search: 'foo', limit: 10 });

    expect(spy).toHaveBeenCalledWith('/transactions', {
      params: { search: 'foo', limit: 10 },
    });
  });

  it('get apunta al endpoint con el id', async () => {
    const spy = vi.spyOn(apiClient, 'get').mockResolvedValue({ data: { id: 'abc' } });

    await transactionsApi.get('abc');

    expect(spy).toHaveBeenCalledWith('/transactions/abc');
  });

  it('create envía el payload', async () => {
    const spy = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: { id: 'new' } });

    await transactionsApi.create({
      account_id: 'acc-1',
      amount: '10.50',
      currency: 'EUR',
      occurred_at: '2026-04-16T00:00:00Z',
    });

    expect(spy).toHaveBeenCalledWith(
      '/transactions',
      expect.objectContaining({ amount: '10.50', currency: 'EUR' }),
    );
  });

  it('update hace PUT al endpoint del recurso', async () => {
    const spy = vi.spyOn(apiClient, 'put').mockResolvedValue({ data: { id: 'abc' } });

    await transactionsApi.update('abc', { amount: '99.99' });

    expect(spy).toHaveBeenCalledWith('/transactions/abc', { amount: '99.99' });
  });

  it('remove hace DELETE al endpoint del recurso', async () => {
    const spy = vi.spyOn(apiClient, 'delete').mockResolvedValue({ data: null });

    await transactionsApi.remove('abc');

    expect(spy).toHaveBeenCalledWith('/transactions/abc');
  });
});
