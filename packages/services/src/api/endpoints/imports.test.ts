import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from '../client';
import { importsApi } from './imports';

describe('importsApi', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('list pasa los params al endpoint', async () => {
    const spy = vi
      .spyOn(apiClient, 'get')
      .mockResolvedValue({ data: { items: [], total: 0, limit: 50, offset: 0 } });

    await importsApi.list({ limit: 10, offset: 20 });

    expect(spy).toHaveBeenCalledWith('/imports', {
      params: { limit: 10, offset: 20 },
    });
  });

  it('get apunta al endpoint con el id', async () => {
    const spy = vi.spyOn(apiClient, 'get').mockResolvedValue({ data: { id: 'job-1' } });

    await importsApi.get('job-1');

    expect(spy).toHaveBeenCalledWith('/imports/job-1');
  });

  it('create envía multipart con file, mappings, currency y category opcional', async () => {
    const spy = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: { id: 'new-job' } });

    const file = new File(['amount,date\n10,2026-01-01'], 'movs.csv', {
      type: 'text/csv',
    });
    await importsApi.create({
      accountId: 'acc-1',
      file,
      columnMappings: {
        amount: 'amount',
        occurred_at: 'date',
        description: null,
        category_name: null,
        statement_balance: 'Saldo',
      },
      currency: 'EUR',
      defaultCategoryId: 'cat-1',
    });

    expect(spy).toHaveBeenCalledTimes(1);
    const [path, body] = spy.mock.calls[0]!;
    expect(path).toBe('/imports');
    expect(body).toBeInstanceOf(FormData);
    const formData = body as FormData;
    expect(formData.get('file')).toBe(file);
    expect(formData.get('currency')).toBe('EUR');
    expect(formData.get('default_category_id')).toBe('cat-1');
    const mappings = JSON.parse(String(formData.get('column_mappings'))) as Record<
      string,
      unknown
    >;
    expect(mappings.amount).toBe('amount');
    expect(mappings.occurred_at).toBe('date');
    expect(mappings.statement_balance).toBe('Saldo');
  });

  it('create omite default_category_id cuando no se pasa', async () => {
    const spy = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: { id: 'new-job' } });

    const file = new File(['x'], 'x.csv', { type: 'text/csv' });
    await importsApi.create({
      accountId: 'acc-1',
      file,
      columnMappings: { amount: 'a', occurred_at: 'b' },
      currency: 'USD',
    });

    const formData = spy.mock.calls[0]?.[1] as FormData;
    expect(formData.get('default_category_id')).toBeNull();
    expect(formData.get('currency')).toBe('USD');
  });

  it('preview envía multipart al endpoint /imports/preview', async () => {
    const spy = vi.spyOn(apiClient, 'post').mockResolvedValue({
      data: {
        job_id: 'job-1',
        source: 'csv',
        total_rows: 0,
        rows: [],
      },
    });

    const file = new File(['x'], 'x.csv', { type: 'text/csv' });
    await importsApi.preview({
      accountId: 'acc-1',
      file,
      columnMappings: { amount: 'a', occurred_at: 'b' },
      currency: 'EUR',
    });

    const [path, body] = spy.mock.calls[0]!;
    expect(path).toBe('/imports/preview');
    expect(body).toBeInstanceOf(FormData);
    const formData = body as FormData;
    expect(formData.get('file')).toBe(file);
    // force_vision se omite si no se pide
    expect(formData.get('force_vision')).toBeNull();
  });

  it('preview con forceVision añade el flag al multipart', async () => {
    const spy = vi.spyOn(apiClient, 'post').mockResolvedValue({
      data: { job_id: 'job-1', source: 'vision', total_rows: 0, rows: [] },
    });

    const file = new File(['x'], 'x.pdf', { type: 'application/pdf' });
    await importsApi.preview({
      accountId: 'acc-1',
      file,
      columnMappings: { amount: 'a', occurred_at: 'b' },
      currency: 'EUR',
      forceVision: true,
    });

    const formData = spy.mock.calls[0]?.[1] as FormData;
    expect(formData.get('force_vision')).toBe('true');
  });

  it('commit POSTea a /imports/{id}/commit con timeout extendido', async () => {
    const spy = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: { id: 'job-1' } });

    await importsApi.commit('job-1');

    expect(spy).toHaveBeenCalledTimes(1);
    const [path, body, config] = spy.mock.calls[0]!;
    expect(path).toBe('/imports/job-1/commit');
    expect(body).toBeUndefined();
    expect((config as { timeout?: number } | undefined)?.timeout).toBeGreaterThan(15_000);
  });
});
