import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from '../client';
import { receiptsApi } from './receipts';

describe('receiptsApi', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('list pasa los params al endpoint', async () => {
    const spy = vi
      .spyOn(apiClient, 'get')
      .mockResolvedValue({ data: { items: [], total: 0, limit: 50, offset: 0 } });

    await receiptsApi.list({ limit: 10, offset: 20 });

    expect(spy).toHaveBeenCalledWith('/receipts', {
      params: { limit: 10, offset: 20 },
    });
  });

  it('get apunta al endpoint con el id', async () => {
    const spy = vi.spyOn(apiClient, 'get').mockResolvedValue({ data: { id: 'r1' } });

    await receiptsApi.get('r1');

    expect(spy).toHaveBeenCalledWith('/receipts/r1');
  });

  it('extract envía multipart con el fichero', async () => {
    const spy = vi
      .spyOn(apiClient, 'post')
      .mockResolvedValue({ data: { receipt: { id: 'r1' }, extraction: { total: '1' } } });
    const file = new File([new Uint8Array([0xff, 0xd8])], 'ticket.jpg', {
      type: 'image/jpeg',
    });

    await receiptsApi.extract(file);

    expect(spy).toHaveBeenCalledTimes(1);
    const [path, body] = spy.mock.calls[0]!;
    expect(path).toBe('/receipts/extract');
    expect(body).toBeInstanceOf(FormData);
    const fd = body as FormData;
    expect(fd.get('file')).toBe(file);
  });

  it('confirm envía el payload al endpoint correspondiente', async () => {
    const spy = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: { id: 'r1' } });

    await receiptsApi.confirm('r1', {
      amount: '10.00',
      occurred_at: '2026-04-15T00:00:00Z',
      currency: 'EUR',
    });

    expect(spy).toHaveBeenCalledWith(
      '/receipts/r1/confirm',
      expect.objectContaining({ amount: '10.00', currency: 'EUR' }),
    );
  });

  it('reject hace POST sin body al endpoint correspondiente', async () => {
    const spy = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: { id: 'r1' } });

    await receiptsApi.reject('r1');

    expect(spy).toHaveBeenCalledWith('/receipts/r1/reject');
  });
});
