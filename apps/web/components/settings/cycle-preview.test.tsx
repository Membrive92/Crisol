import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type * as ServicesModule from '@crisol/services';
import type { Transaction, TransactionListQuery } from '@crisol/types';

/*
 * C2 — La previsualización del corte.
 *
 * Lo que se prueba aquí no es cosmético: son las DOS ventanas que se le piden
 * al servidor. Si el tope del ciclo saliente fuese el día del corte en vez del
 * segundo anterior, el primer día del ciclo nuevo saldría contado a los dos
 * lados; y si el ciclo entrante se pidiera en `desc`, la pantalla enseñaría sus
 * ÚLTIMOS movimientos donde promete los primeros — que es justo donde el
 * usuario busca su nómina.
 *
 * `todayDayStr` se fija: la previsualización ancla en el ciclo EN CURSO, así
 * que sin fijar el reloj este test cambiaría de respuesta cada día (la bomba de
 * relojería de [AUDIT-2026-08]). La aritmética del ciclo es la REAL, no un
 * doble: es la que decide las fechas que se afirman abajo.
 */

const calls: TransactionListQuery[] = [];
let rows: Transaction[] = [];
let total = 0;
let isPlaceholderData = false;

vi.mock('@crisol/services', async (importOriginal) => {
  const actual = await importOriginal<typeof ServicesModule>();
  return {
    ...actual,
    todayDayStr: () => '2026-08-20',
    useTransactions: (query: TransactionListQuery) => {
      calls.push(query);
      return {
        data: { items: rows, total, limit: 5, offset: 0 },
        isLoading: false,
        isError: false,
        error: null,
        // El hook lleva `placeholderData: (previous) => previous`, así que
        // mientras pide los datos del día NUEVO sigue devolviendo los del
        // viejo con este flag en `true`. El mock lo expone para poder probarlo.
        isPlaceholderData,
      };
    },
  };
});

import { CyclePreview } from './cycle-preview';

function tx(over: Partial<Transaction> = {}): Transaction {
  return {
    id: 'tx-1',
    user_id: 'u-1',
    account_id: 'acc-1',
    category_id: null,
    transfer_pair_id: null,
    deferred_by_account_id: null,
    amount: '2520.68',
    currency: 'EUR',
    occurred_at: '2026-08-14T10:00:00Z',
    description: 'NOMINA AGOSTO',
    source: 'import',
    flow: 'IN',
    receipt_id: null,
    created_at: '2026-08-14T10:00:00Z',
    updated_at: '2026-08-14T10:00:00Z',
    deleted_at: null,
    converted_amount: null,
    converted_currency: null,
    is_debt_pair: false,
    ...over,
  };
}

beforeEach(() => {
  calls.length = 0;
  rows = [];
  total = 0;
  isPlaceholderData = false;
});

describe('CyclePreview · las dos ventanas que se piden', () => {
  it('acota los dos lados del corte y pide cada uno en su sentido', () => {
    render(<CyclePreview cycleStartDay={14} />);

    expect(calls).toHaveLength(2);

    // Ciclo SALIENTE (14 jul → 13 ago): sus ÚLTIMAS filas, de ahí `desc`.
    // `date_to` es el corte MENOS UN SEGUNDO — el intervalo del backend es
    // cerrado por los dos extremos.
    expect(calls[0]).toEqual({
      date_from: '2026-07-14T00:00:00.000Z',
      date_to: '2026-08-13T23:59:59.000Z',
      order: 'desc',
      limit: 5,
    });

    // Ciclo ENTRANTE (14 ago → 13 sep): sus PRIMERAS filas, de ahí `asc`.
    expect(calls[1]).toEqual({
      date_from: '2026-08-14T00:00:00.000Z',
      date_to: '2026-09-13T23:59:59.000Z',
      order: 'asc',
      limit: 5,
    });
  });

  it('el corte del saliente y el del entrante no se solapan ni dejan hueco', () => {
    render(<CyclePreview cycleStartDay={14} />);

    const outgoingTo = calls[0]?.date_to ?? '';
    const incomingFrom = calls[1]?.date_from ?? '';
    expect(new Date(incomingFrom).getTime() - new Date(outgoingTo).getTime()).toBe(1000);
  });

  it('etiqueta cada lado por su día de cobro, con el rango completo a la vista', () => {
    render(<CyclePreview cycleStartDay={14} />);

    expect(screen.getByText(/Ciclo del 14 jul 2026/)).toBeDefined();
    expect(screen.getByText(/Ciclo del 14 ago 2026/)).toBeDefined();
    expect(screen.getByText(/14 jul .* 13 ago 2026/)).toBeDefined();
    expect(screen.getByText(/14 ago .* 13 sep 2026/)).toBeDefined();
  });

  it('el recuento sale del total del servidor, no de las filas pedidas', () => {
    // 5 filas en pantalla, 37 en el ciclo: el `total` no es `items.length`.
    rows = [tx()];
    total = 37;
    render(<CyclePreview cycleStartDay={14} />);

    expect(screen.getAllByText('37 movimientos caen en este ciclo')).toHaveLength(2);
  });

  it('un ciclo con un solo movimiento no dice «1 movimientos»', () => {
    rows = [tx()];
    total = 1;
    render(<CyclePreview cycleStartDay={14} />);

    expect(screen.getAllByText('1 movimiento cae en este ciclo')).toHaveLength(2);
  });

  it('pinta la fila con su fecha, su concepto y su importe', () => {
    rows = [tx()];
    total = 1;
    render(<CyclePreview cycleStartDay={14} />);

    // Las TRES cosas, no sólo el concepto: la fecha y el importe son
    // precisamente con lo que el usuario reconoce su nómina a cada lado del
    // corte. Con sólo el concepto afirmado, la previsualización podía quedarse
    // pintando una lista de descripciones sin fecha ni importe —inútil para
    // decidir el día— con el nombre del test diciendo que las pinta.
    expect(screen.getAllByText('NOMINA AGOSTO').length).toBeGreaterThan(0);
    expect(screen.getAllByText('14/08/2026').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/2520,68/).length).toBeGreaterThan(0);
  });

  /*
   * El día 1 degenera en el mes natural — es el invariante 2 de `cycle-period`.
   * Aquí se comprueba de punta a punta: si la previsualización lo tradujera mal,
   * el usuario que elige el 1 vería un corte que no coincide con el mes que ya
   * conoce, y desconfiaría de todo lo demás.
   */
  it('mientras llegan los datos del día nuevo NO pinta el recuento del viejo', () => {
    // El hook conserva los datos anteriores mientras pide los nuevos
    // (`placeholderData`), así que al cambiar el día la pantalla tenía debajo
    // del titular «Ciclo del 20 ago» el recuento de la ventana del 14 — y sin
    // ningún indicador de carga. Es decir, atribuía un número a un ciclo que no
    // es el suyo, justo en el gesto que esta pantalla existe para sostener.
    // Este fichero declara la regla que eso incumplía: una cifra falsa cuesta
    // más que un hueco, porque el hueco se pregunta y la cifra se cree.
    rows = [tx()];
    total = 37;
    isPlaceholderData = true;
    render(<CyclePreview cycleStartDay={14} />);

    expect(screen.queryByText('37 movimientos caen en este ciclo')).toBeNull();
    expect(screen.queryByText('NOMINA AGOSTO')).toBeNull();
    expect(screen.getAllByText(/Cargando/i).length).toBeGreaterThan(0);
  });

  it('con el día 1 el corte es exactamente el mes natural', () => {
    render(<CyclePreview cycleStartDay={1} />);

    expect(calls[0]).toEqual({
      date_from: '2026-07-01T00:00:00.000Z',
      date_to: '2026-07-31T23:59:59.000Z',
      order: 'desc',
      limit: 5,
    });
    expect(calls[1]).toEqual({
      date_from: '2026-08-01T00:00:00.000Z',
      date_to: '2026-08-31T23:59:59.000Z',
      order: 'asc',
      limit: 5,
    });
  });
});
