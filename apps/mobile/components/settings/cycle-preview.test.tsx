// @types/jest expone los globals (describe/it/expect/jest) — sin import.
import { render } from '@testing-library/react-native';

import type * as ServicesModule from '@crisol/services';
import type { Transaction, TransactionListQuery } from '@crisol/types';

/*
 * C2 (móvil) — La previsualización del corte.
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

const mockCalls: TransactionListQuery[] = [];
const mockState: { rows: Transaction[]; total: number; isPlaceholderData: boolean } = {
  rows: [],
  total: 0,
  isPlaceholderData: false,
};

jest.mock('@crisol/services', () => {
  const actual = jest.requireActual<typeof ServicesModule>('@crisol/services');
  return {
    ...actual,
    todayDayStr: () => '2026-08-20',
    useTransactions: (query: TransactionListQuery) => {
      mockCalls.push(query);
      return {
        data: { items: mockState.rows, total: mockState.total, limit: 5, offset: 0 },
        isLoading: false,
        isError: false,
        error: null,
        // El hook lleva `placeholderData: (previous) => previous`, así que
        // mientras pide los datos del día NUEVO sigue devolviendo los del
        // viejo con este flag en `true`. El mock lo expone para poder probarlo.
        isPlaceholderData: mockState.isPlaceholderData,
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
  mockCalls.length = 0;
  mockState.rows = [];
  mockState.total = 0;
  mockState.isPlaceholderData = false;
});

describe('CyclePreview (móvil) · las dos ventanas que se piden', () => {
  it('acota los dos lados del corte y pide cada uno en su sentido', () => {
    render(<CyclePreview cycleStartDay={14} />);

    expect(mockCalls).toHaveLength(2);

    // Ciclo SALIENTE (14 jul → 13 ago): sus ÚLTIMAS filas, de ahí `desc`.
    // `date_to` es el corte MENOS UN SEGUNDO — el intervalo del backend es
    // cerrado por los dos extremos.
    expect(mockCalls[0]).toEqual({
      date_from: '2026-07-14T00:00:00.000Z',
      date_to: '2026-08-13T23:59:59.000Z',
      order: 'desc',
      limit: 5,
    });

    // Ciclo ENTRANTE (14 ago → 13 sep): sus PRIMERAS filas, de ahí `asc`.
    expect(mockCalls[1]).toEqual({
      date_from: '2026-08-14T00:00:00.000Z',
      date_to: '2026-09-13T23:59:59.000Z',
      order: 'asc',
      limit: 5,
    });
  });

  it('el corte del saliente y el del entrante no se solapan ni dejan hueco', () => {
    render(<CyclePreview cycleStartDay={14} />);

    const outgoingTo = mockCalls[0]?.date_to ?? '';
    const incomingFrom = mockCalls[1]?.date_from ?? '';
    expect(new Date(incomingFrom).getTime() - new Date(outgoingTo).getTime()).toBe(1000);
  });

  it('etiqueta cada lado por su día de cobro, con el rango completo a la vista', () => {
    const { getByText } = render(<CyclePreview cycleStartDay={14} />);

    expect(getByText(/Ciclo del 14 jul 2026/)).toBeTruthy();
    expect(getByText(/Ciclo del 14 ago 2026/)).toBeTruthy();
    expect(getByText(/14 jul .* 13 ago 2026/)).toBeTruthy();
    expect(getByText(/14 ago .* 13 sep 2026/)).toBeTruthy();
  });

  it('el recuento sale del total del servidor, no de las filas pedidas', () => {
    // 1 fila en pantalla, 37 en el ciclo: el `total` no es `items.length`.
    mockState.rows = [tx()];
    mockState.total = 37;
    const { getAllByText } = render(<CyclePreview cycleStartDay={14} />);

    expect(getAllByText('37 movimientos caen en este ciclo')).toHaveLength(2);
  });

  it('un ciclo con un solo movimiento no dice «1 movimientos»', () => {
    mockState.rows = [tx()];
    mockState.total = 1;
    const { getAllByText } = render(<CyclePreview cycleStartDay={14} />);

    expect(getAllByText('1 movimiento cae en este ciclo')).toHaveLength(2);
  });

  it('pinta la fila con su fecha, su concepto y su importe', () => {
    mockState.rows = [tx()];
    mockState.total = 1;
    const { getAllByText } = render(<CyclePreview cycleStartDay={14} />);

    // Las TRES cosas, no sólo el concepto: la fecha y el importe son
    // precisamente con lo que el usuario reconoce su nómina a cada lado del
    // corte. Con sólo el concepto afirmado, la previsualización podía quedarse
    // pintando una lista de descripciones sin fecha ni importe —inútil para
    // decidir el día— con el nombre del test diciendo que las pinta.
    expect(getAllByText('NOMINA AGOSTO').length).toBeGreaterThan(0);
    expect(getAllByText('14/08/2026').length).toBeGreaterThan(0);
    expect(getAllByText(/2520,68/).length).toBeGreaterThan(0);
  });

  it('mientras llegan los datos del día nuevo NO pinta el recuento del viejo', () => {
    // El hook conserva los datos anteriores mientras pide los nuevos
    // (`placeholderData`), así que al cambiar el día la pantalla tenía debajo
    // del titular «Ciclo del 20 ago» el recuento de la ventana del 14 — y sin
    // ningún indicador de carga. Es decir, atribuía un número a un ciclo que no
    // es el suyo, justo en el gesto que esta pantalla existe para sostener: una
    // cifra falsa cuesta más que un hueco, porque el hueco se pregunta y la
    // cifra se cree. Se corrigió en web; aquí queda atado para que móvil no lo
    // reintroduzca.
    mockState.rows = [tx()];
    mockState.total = 37;
    mockState.isPlaceholderData = true;
    const { getAllByText, queryByText } = render(<CyclePreview cycleStartDay={14} />);

    expect(queryByText('37 movimientos caen en este ciclo')).toBeNull();
    expect(queryByText('NOMINA AGOSTO')).toBeNull();
    expect(getAllByText(/Cargando/i).length).toBeGreaterThan(0);
  });

  /*
   * El día 1 degenera en el mes natural — es el invariante 2 de `cycle-period`.
   * Aquí se comprueba de punta a punta: si la previsualización lo tradujera mal,
   * el usuario que elige el 1 vería un corte que no coincide con el mes que ya
   * conoce, y desconfiaría de todo lo demás.
   */
  it('con el día 1 el corte es exactamente el mes natural', () => {
    render(<CyclePreview cycleStartDay={1} />);

    expect(mockCalls[0]).toEqual({
      date_from: '2026-07-01T00:00:00.000Z',
      date_to: '2026-07-31T23:59:59.000Z',
      order: 'desc',
      limit: 5,
    });
    expect(mockCalls[1]).toEqual({
      date_from: '2026-08-01T00:00:00.000Z',
      date_to: '2026-08-31T23:59:59.000Z',
      order: 'asc',
      limit: 5,
    });
  });
});
