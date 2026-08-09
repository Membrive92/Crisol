import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactElement } from 'react';
import { describe, expect, it, vi } from 'vitest';

import { investmentApi, queryKeys } from '@crisol/services';
import type { SecuritySearchHit, SecuritySearchResponse } from '@crisol/types';

import { SecuritySearch } from './security-search';

/**
 * Buscador por capas (PHASE-44.8 E2).
 *
 * Los datos se siembran en la caché de TanStack Query, no mockeando el cliente
 * HTTP: el hook importa el módulo de endpoints por ruta interna, así que
 * sustituir el `investmentApi` del índice del paquete no le afecta (está
 * documentado en `add-lot-form.test.tsx`, donde costó un falso rojo).
 */

function makeHit(overrides: Partial<SecuritySearchHit> = {}): SecuritySearchHit {
  return {
    id: null,
    ticker: 'MCD',
    exchange: 'NYSE',
    exchange_label: 'NYSE',
    name: 'MCDONALDS CORP',
    in_catalog: false,
    source: 'sec_index',
    cik: '0000063908',
    isin: null,
    currency: null,
    listing_key: 'idx:NYSE:MCD',
    analysis_available: true,
    analysis_reason: null,
    ...overrides,
  };
}

function makeResponse(overrides: Partial<SecuritySearchResponse> = {}): SecuritySearchResponse {
  return {
    results: [makeHit()],
    external_search_available: false,
    index_ready: true,
    notice: null,
    directory_seeded_at: '2026-08-07T12:00:00Z',
    ...overrides,
  };
}

function renderSeeded(
  node: ReactElement,
  seed: [string, SecuritySearchResponse],
): void {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 60_000 } },
  });
  client.setQueryData(queryKeys.investment.search(seed[0]), seed[1]);
  render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
}

describe('SecuritySearch', () => {
  it('adopta por listing_key y NO por el ticker suelto', async () => {
    // La diferencia no es cosmética: el ticker no lleva plaza, así que MCD
    // entraba en el catálogo como `UNKNOWN` en vez de `NYSE`. La clave sí la
    // lleva, y es lo que impide además que el cliente decida el mercado.
    const adopt = vi
      .spyOn(investmentApi, 'adoptSecurity')
      .mockResolvedValue({ id: 'sec-9' } as never);
    const resolve = vi.spyOn(investmentApi, 'resolveSecurity');
    const onSelect = vi.fn();

    renderSeeded(<SecuritySearch onSelect={onSelect} />, ['MCD', makeResponse()]);
    await userEvent.type(screen.getByRole('combobox', { name: 'Buscar valor' }), 'MCD');
    await userEvent.click(await screen.findByText(/MCDONALDS CORP/));

    expect(adopt).toHaveBeenCalledWith({ listing_key: 'idx:NYSE:MCD' });
    expect(resolve).not.toHaveBeenCalled();
    expect(onSelect).toHaveBeenCalledWith('sec-9');
  });

  it('una fila que ya está en el catálogo se elige sin pedir nada al servidor', async () => {
    const adopt = vi.spyOn(investmentApi, 'adoptSecurity');
    const onSelect = vi.fn();
    const response = makeResponse({
      results: [makeHit({ id: 'sec-1', in_catalog: true, source: 'catalog' })],
    });

    renderSeeded(<SecuritySearch onSelect={onSelect} />, ['MCD', response]);
    await userEvent.type(screen.getByRole('combobox', { name: 'Buscar valor' }), 'MCD');
    await userEvent.click(await screen.findByText(/MCDONALDS CORP/));

    expect(adopt).not.toHaveBeenCalled();
    expect(onSelect).toHaveBeenCalledWith('sec-1');
  });

  it('explica por qué no encuentra Inditex en vez de dejar el hueco en blanco', async () => {
    // Un desplegable vacío se lee como «esa empresa no existe», que es falso:
    // lo que pasa es que Inditex no es un emisor de la SEC.
    const response = makeResponse({
      results: [],
      notice: '«ITX» es el ticker de Inditex en su mercado local.',
    });

    renderSeeded(<SecuritySearch onSelect={vi.fn()} />, ['ITX', response]);
    await userEvent.type(screen.getByRole('combobox', { name: 'Buscar valor' }), 'ITX');

    expect(await screen.findByText(/Inditex/)).toBeTruthy();
  });

  it('si el índice no cargó lo dice, en vez de afirmar que no hay coincidencias', async () => {
    const response = makeResponse({ results: [], index_ready: false });

    renderSeeded(<SecuritySearch onSelect={vi.fn()} />, ['MCD', response]);
    await userEvent.type(screen.getByRole('combobox', { name: 'Buscar valor' }), 'MCD');

    expect(await screen.findByText(/no está disponible ahora mismo/)).toBeTruthy();
  });

  it('una fila del directorio UE/UK se identifica por nombre, plaza e ISIN', async () => {
    // FIRDS no publica ticker: inventarlo sería un dato falso. La fila se
    // identifica por su identidad registral y se adopta por la clave ext:.
    const adopt = vi
      .spyOn(investmentApi, 'adoptSecurity')
      .mockResolvedValue({ id: 'sec-eu' } as never);
    const onSelect = vi.fn();
    const response = makeResponse({
      results: [
        makeHit({
          ticker: '',
          name: 'INDUSTRIA DE DISEÑO TEXTIL S.A. INDITEX',
          exchange: 'XMAD',
          exchange_label: 'XMAD',
          source: 'eu_directory',
          cik: null,
          isin: 'ES0148396007',
          currency: 'EUR',
          listing_key: 'ext:XMAD:ES0148396007',
          analysis_available: false,
          analysis_reason: 'Sin filings en EDGAR.',
        }),
      ],
    });

    renderSeeded(<SecuritySearch onSelect={onSelect} />, ['inditex', response]);
    await userEvent.type(screen.getByRole('combobox', { name: 'Buscar valor' }), 'inditex');

    expect(await screen.findByText(/ES0148396007/)).toBeTruthy();
    await userEvent.click(screen.getByText(/INDITEX/));
    expect(adopt).toHaveBeenCalledWith({ listing_key: 'ext:XMAD:ES0148396007' });
    expect(onSelect).toHaveBeenCalledWith('sec-eu');
  });

  it('la degradación ticker_required pide el símbolo y reintenta con él', async () => {
    // El caso Unilever del spike: el proveedor no reconoce el ISIN. El 422
    // trae la identidad pre-rellenada; el usuario escribe el símbolo local y el
    // alta se completa validada.
    const detail = {
      code: 'ticker_required',
      message: 'El proveedor de precios no reconoce este ISIN.',
      prefill: { isin: 'GB00B10RZP78', mic: 'XLON', name: 'UNILEVER PLC', currency: 'GBP' },
    };
    const adopt = vi
      .spyOn(investmentApi, 'adoptSecurity')
      .mockRejectedValueOnce({ response: { data: { detail } } })
      .mockResolvedValueOnce({ id: 'sec-uk' } as never);
    const onSelect = vi.fn();
    const response = makeResponse({
      results: [
        makeHit({
          ticker: '',
          name: 'UNILEVER PLC',
          exchange: 'XLON',
          exchange_label: 'XLON',
          source: 'eu_directory',
          cik: null,
          isin: 'GB00B10RZP78',
          currency: 'GBP',
          listing_key: 'ext:XLON:GB00B10RZP78',
          analysis_available: false,
        }),
      ],
    });

    renderSeeded(<SecuritySearch onSelect={onSelect} />, ['unilever', response]);
    await userEvent.type(screen.getByRole('combobox', { name: 'Buscar valor' }), 'unilever');
    await userEvent.click(await screen.findByText(/UNILEVER PLC/));

    // El formulario de degradación aparece con la identidad del directorio.
    const tickerInput = await screen.findByPlaceholderText(/Símbolo local/);
    await userEvent.type(tickerInput, 'ulvr');
    await userEvent.click(screen.getByText('Añadir'));

    expect(adopt).toHaveBeenLastCalledWith({
      listing_key: 'ext:XLON:GB00B10RZP78',
      ticker: 'ULVR',
    });
    expect(onSelect).toHaveBeenCalledWith('sec-uk');
  });

  it('cambiar la búsqueda descarta el formulario de ticker pendiente', async () => {
    // Si el formulario sobrevive al cambio de consulta, queda apuntando al
    // listing anterior: pulsar «Añadir» daría de alta el valor equivocado.
    const detail = {
      code: 'ticker_required',
      message: 'El proveedor de precios no reconoce este ISIN.',
      prefill: { isin: 'GB00B10RZP78', mic: 'XLON', name: 'UNILEVER PLC', currency: 'GBP' },
    };
    vi.spyOn(investmentApi, 'adoptSecurity').mockRejectedValue({ response: { data: { detail } } });
    const response = makeResponse({
      results: [
        makeHit({
          ticker: '',
          name: 'UNILEVER PLC',
          source: 'eu_directory',
          isin: 'GB00B10RZP78',
          listing_key: 'ext:XLON:GB00B10RZP78',
        }),
      ],
    });

    renderSeeded(<SecuritySearch onSelect={vi.fn()} />, ['unilever', response]);
    const box = screen.getByRole('combobox', { name: 'Buscar valor' });
    await userEvent.type(box, 'unilever');
    await userEvent.click(await screen.findByText(/UNILEVER PLC/));
    expect(await screen.findByPlaceholderText(/Símbolo local/)).toBeTruthy();

    await userEvent.type(box, 'x');

    expect(screen.queryByPlaceholderText(/Símbolo local/)).toBeNull();
  });

  it('se puede recorrer y elegir entero con el teclado', async () => {
    // Criterio de aceptación de la E3: sin ratón. ↓ mueve el foco virtual y
    // Enter elige la fila activa.
    const adopt = vi
      .spyOn(investmentApi, 'adoptSecurity')
      .mockResolvedValue({ id: 'sec-2' } as never);
    const onSelect = vi.fn();
    const response = makeResponse({
      results: [
        makeHit({ name: 'PRIMERA', listing_key: 'idx:NYSE:AAA' }),
        makeHit({ name: 'SEGUNDA', listing_key: 'idx:NYSE:BBB' }),
      ],
    });

    renderSeeded(<SecuritySearch onSelect={onSelect} />, ['mc', response]);
    const box = screen.getByRole('combobox', { name: 'Buscar valor' });
    await userEvent.type(box, 'mc');
    await screen.findByText(/PRIMERA/);

    await userEvent.keyboard('{ArrowDown}{Enter}');

    expect(adopt).toHaveBeenCalledWith({ listing_key: 'idx:NYSE:BBB' });
    expect(onSelect).toHaveBeenCalledWith('sec-2');
  });

  it('la opción activa se anuncia con aria-activedescendant', async () => {
    const response = makeResponse({
      results: [
        makeHit({ name: 'PRIMERA', listing_key: 'idx:NYSE:AAA' }),
        makeHit({ name: 'SEGUNDA', listing_key: 'idx:NYSE:BBB' }),
      ],
    });

    renderSeeded(<SecuritySearch onSelect={vi.fn()} />, ['mc', response]);
    const box = screen.getByRole('combobox', { name: 'Buscar valor' });
    await userEvent.type(box, 'mc');
    await screen.findByText(/PRIMERA/);

    const first = box.getAttribute('aria-activedescendant');
    await userEvent.keyboard('{ArrowDown}');
    const second = box.getAttribute('aria-activedescendant');

    expect(first).toBeTruthy();
    expect(second).toBeTruthy();
    expect(second).not.toBe(first);
    // Y apunta a una opción que existe de verdad, no a un id inventado.
    expect(document.getElementById(second as string)?.getAttribute('role')).toBe('option');
  });

  it('en Análisis, lo que no se puede analizar sale apagado y con el motivo VISIBLE', async () => {
    // Elegir SPY en Análisis lleva a un callejón: tiene CIK, así que la ingesta
    // se lanza y falla, y el mensaje manda a lanzarla otra vez. En Cartera, en
    // cambio, es un valor perfectamente válido.
    const adopt = vi.spyOn(investmentApi, 'adoptSecurity');
    const response = makeResponse({
      results: [
        makeHit({
          ticker: 'SPY',
          name: 'SPDR S&P 500 ETF TRUST',
          analysis_available: false,
          analysis_reason: 'No presenta cuentas anuales (10-K).',
          listing_key: 'idx:NYSE:SPY',
        }),
      ],
    });

    renderSeeded(<SecuritySearch intent="analysis" onSelect={vi.fn()} />, ['SPY', response]);
    await userEvent.type(screen.getByRole('combobox', { name: 'Buscar valor' }), 'SPY');

    const option = await screen.findByRole('option');
    expect(option.getAttribute('aria-disabled')).toBe('true');
    // El motivo se PINTA, no vive en un `title` que en táctil no existe.
    expect(screen.getByText(/No presenta cuentas anuales/)).toBeTruthy();

    await userEvent.click(option);
    expect(adopt).not.toHaveBeenCalled();
  });

  it('...y en Cartera ese mismo valor sí se puede elegir', async () => {
    const adopt = vi
      .spyOn(investmentApi, 'adoptSecurity')
      .mockResolvedValue({ id: 'sec-spy' } as never);
    const response = makeResponse({
      results: [
        makeHit({
          ticker: 'SPY',
          name: 'SPDR S&P 500 ETF TRUST',
          analysis_available: false,
          analysis_reason: 'No presenta cuentas anuales (10-K).',
          listing_key: 'idx:NYSE:SPY',
        }),
      ],
    });

    renderSeeded(<SecuritySearch intent="portfolio" onSelect={vi.fn()} />, ['SPY', response]);
    await userEvent.type(screen.getByRole('combobox', { name: 'Buscar valor' }), 'SPY');

    const option = await screen.findByRole('option');
    expect(option.getAttribute('aria-disabled')).toBe('false');
    await userEvent.click(option);
    expect(adopt).toHaveBeenCalledWith({ listing_key: 'idx:NYSE:SPY' });
  });

  it('marca las filas que sólo sirven para cartera', async () => {
    const response = makeResponse({
      results: [
        makeHit({
          ticker: 'SPY',
          name: 'SPDR S&P 500 ETF TRUST',
          analysis_available: false,
          analysis_reason: 'No presenta cuentas anuales.',
          listing_key: 'idx:NYSE:SPY',
        }),
      ],
    });

    renderSeeded(<SecuritySearch onSelect={vi.fn()} />, ['SPY', response]);
    await userEvent.type(screen.getByRole('combobox', { name: 'Buscar valor' }), 'SPY');

    expect(await screen.findByText('sólo cartera')).toBeTruthy();
  });
});
