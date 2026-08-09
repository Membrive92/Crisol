// @types/jest expone los globals (describe/it/expect) — sin import.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, waitFor } from '@testing-library/react-native';
import type { ReactElement } from 'react';

import { investmentApi, queryKeys } from '@crisol/services';
import type { SecuritySearchResponse } from '@crisol/types';

import { AddLotForm } from './add-lot-form';

/**
 * Alta de compra en móvil (PHASE-44.8 E4).
 *
 * La pantalla de Cartera era de sólo lectura y decía «añádelas desde la web».
 * Estos tests fijan lo que hace el formulario nuevo, y sobre todo lo que NO
 * hace: mandar una compra a medias.
 */

const hit: SecuritySearchResponse = {
  results: [
    {
      id: 'sec-1',
      ticker: 'MCD',
      exchange: 'NYSE',
      exchange_label: 'NYSE',
      name: 'MCDONALDS CORP',
      in_catalog: true,
      source: 'catalog',
      cik: '0000063908',
      isin: null,
      currency: null,
      listing_key: 'cat:sec-1',
      analysis_available: true,
      analysis_reason: null,
    },
  ],
  external_search_available: false,
  index_ready: true,
  notice: null,
  directory_seeded_at: null,
};

function renderSeeded(node: ReactElement, seed?: [string, SecuritySearchResponse]) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 60_000 } },
  });
  if (seed) client.setQueryData(queryKeys.investment.search(seed[0]), seed[1]);
  return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
}

describe('AddLotForm (móvil)', () => {
  it('no envía nada hasta tener valor, cantidad, precio y fecha', () => {
    const create = jest.spyOn(investmentApi, 'createLot');
    const { getByText } = renderSeeded(<AddLotForm onDone={jest.fn()} />);

    fireEvent.press(getByText('Añadir compra'));

    expect(create).not.toHaveBeenCalled();
  });

  it('avisa de una fecha con formato incorrecto en vez de mandarla', () => {
    const { getByPlaceholderText, getByText } = renderSeeded(<AddLotForm onDone={jest.fn()} />);

    fireEvent.changeText(getByPlaceholderText('AAAA-MM-DD'), '07/08/2026');

    expect(getByText(/AAAA-MM-DD \(p. ej./)).toBeTruthy();
  });

  it('acepta la coma decimal y la manda con punto', async () => {
    // En un teclado español la coma es lo natural; el backend espera `Decimal`
    // serializado con punto. Sin la conversión, `12,5` llega como texto roto.
    const create = jest
      .spyOn(investmentApi, 'createLot')
      .mockResolvedValue({ id: 'lot-1' } as never);
    const onDone = jest.fn();
    const { getByPlaceholderText, getByText, findByText } = renderSeeded(
      <AddLotForm onDone={onDone} />,
      ['MCD', hit],
    );

    // Elegir el valor por el buscador. `findByText` espera al debounce de
    // 250 ms del hook — con `getByText` el desplegable aún no existe.
    fireEvent.changeText(getByPlaceholderText('Valor de la compra'), 'MCD');
    fireEvent.press(await findByText(/MCDONALDS CORP/));

    fireEvent.changeText(getByPlaceholderText('Cantidad'), '12,5');
    fireEvent.changeText(getByPlaceholderText('Precio'), '250,75');
    fireEvent.press(getByText('Añadir compra'));

    await waitFor(() => expect(create).toHaveBeenCalled());
    expect(create).toHaveBeenCalledWith(
      expect.objectContaining({ security_id: 'sec-1', quantity: '12.5', price: '250.75' }),
    );
  });

  it('no pide el tipo de cambio: lo deriva el servidor', () => {
    // Pedirlo aquí invitaría a rellenarlo con un `1`, que es exactamente el
    // dato ficticio que costó el lote de JNJ (PHASE-44.11).
    const { queryByPlaceholderText } = renderSeeded(<AddLotForm onDone={jest.fn()} />);
    expect(queryByPlaceholderText(/cambio/i)).toBeNull();
    expect(queryByPlaceholderText(/fx/i)).toBeNull();
  });
});
