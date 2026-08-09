import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactElement } from 'react';
import { describe, expect, it, vi } from 'vitest';

import { queryKeys, SEARCH_MIN_LENGTH } from '@crisol/services';
import type { SecuritySearchResponse } from '@crisol/types';

import { AddLotForm } from './add-lot-form';

/**
 * El buscador «no aparecía» en Cartera pese a ser el MISMO componente que en
 * Análisis. El log de uvicorn acotó el problema: estando en Cartera no salía ni
 * una petición, así que fallaba antes de la query — y la causa era que por
 * debajo del mínimo de caracteres el componente no decía absolutamente nada.
 *
 * Los datos se siembran en la caché de TanStack Query en vez de mockear el
 * cliente HTTP: el hook importa el módulo de endpoints por ruta interna, así que
 * sustituir el `investmentApi` del índice del paquete no le afecta (fue el
 * primer intento y daba un falso rojo).
 */

const hit: SecuritySearchResponse = {
  results: [
    {
      id: 'sec-1',
      ticker: 'MCD',
      exchange: 'NYSE',
      name: 'MCDONALDS CORP',
      in_catalog: true,
      analysis_available: true,
      listing_key: 'cat:sec-1',
      source: 'catalog',
      cik: '0000063908',
      isin: null,
      currency: null,
      exchange_label: 'NYSE',
      analysis_reason: null,
    },
  ],
  external_search_available: false,
  index_ready: true,
  notice: null,
  directory_seeded_at: null,
};

function renderWithCache(node: ReactElement, seed?: [string, SecuritySearchResponse]): void {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 60_000 } },
  });
  if (seed) client.setQueryData(queryKeys.investment.search(seed[0]), seed[1]);
  render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
}

describe('AddLotForm', () => {
  it('muestra el buscador de valores al abrirse', () => {
    renderWithCache(<AddLotForm onDone={vi.fn()} />);
    expect(screen.getByPlaceholderText('Valor de la compra')).toBeTruthy();
  });

  it('con una sola letra avisa de que faltan caracteres en vez de callarse', async () => {
    renderWithCache(<AddLotForm onDone={vi.fn()} />);

    await userEvent.type(screen.getByPlaceholderText('Valor de la compra'), 'M');

    expect(screen.getByText(`Escribe al menos ${SEARCH_MIN_LENGTH} caracteres.`)).toBeTruthy();
  });

  it('despliega el valor encontrado y permite elegirlo', async () => {
    renderWithCache(<AddLotForm onDone={vi.fn()} />, ['MCD', hit]);

    await userEvent.type(screen.getByPlaceholderText('Valor de la compra'), 'MCD');

    const row = await screen.findByText(/MCDONALDS CORP/);
    await userEvent.click(row);

    // Elegido: el buscador se repliega y el botón de alta queda disponible.
    expect(screen.getByText('Valor elegido ✓')).toBeTruthy();
  });
});
