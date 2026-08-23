// @types/jest expone los globals (describe/it/expect) — sin import.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, waitFor } from '@testing-library/react-native';
import type { ReactNode } from 'react';

import {
  cycleAnchorContaining,
  cycleDaysForAnchor,
  debtApi,
  periodLabel,
  queryKeys,
  todayDayStr,
} from '@crisol/services';
import type { User } from '@crisol/types';
import { CYCLE_PRESET_LABEL, NATURAL_MONTH_NOTICE } from '@crisol/ui';

/*
 * Los charts y el router se sustituyen porque no aportan nada a lo que se
 * comprueba aquí y sí traen su propio ruido: `react-native-gifted-charts`
 * arrastra un paquete ESM que el `transformIgnorePatterns` de la app no
 * transforma, y `expo-router` exige un contenedor de navegación.
 */
jest.mock('react-native-gifted-charts', () => ({
  BarChart: () => null,
  LineChart: () => null,
  PieChart: () => null,
}));

jest.mock('expo-router', () => ({
  Stack: { Screen: () => null },
  Link: ({ children }: { children: ReactNode }) => children,
  useRouter: () => ({ push: jest.fn(), replace: jest.fn(), back: jest.fn() }),
  useLocalSearchParams: () => ({}),
}));

import DebtScreen from './index';

/*
 * C3a — El preset «Mi ciclo» en la pantalla de Deuda (móvil).
 *
 * Lo que fija este fichero es la TRADUCCIÓN: el backend de deuda no conoce
 * `range=cycle` —su contrato es `month|year|custom`, y mandarle otra cosa da un
 * 422—, así que el ciclo viaja como rango libre día-exacto con las dos fechas
 * que calcula la capa compartida. Es la misma traducción que hace web.
 */

/** Perfil CON ajuste. El día 14 es el caso motivador: la nómina se cobra el 14. */
const USER_WITH_CYCLE: User = {
  id: 'u-1',
  email: 'test@example.com',
  display_name: 'Test',
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  cycle_start_day: 14,
};

/**
 * Perfil de un backend ANTERIOR a la columna: la clave `cycle_start_day` va
 * OMITIDA, no puesta a `null`. Con `null` el test pasaría igual y no probaría
 * nada — el fallo que existe para cazar es `undefined !== null`, que es cierto
 * (lección PHASE-47.E).
 */
const USER_WITHOUT_CYCLE: User = {
  id: 'u-1',
  email: 'test@example.com',
  display_name: 'Test',
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

function renderScreen(user: User) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(queryKeys.auth.me, user);
  return render(
    <QueryClientProvider client={client}>
      <DebtScreen />
    </QueryClientProvider>,
  );
}

/** Última llamada al endpoint de deuda (el que traduce el período). */
function lastSummaryCall(spy: jest.SpyInstance): Record<string, unknown> {
  const calls = spy.mock.calls;
  return calls[calls.length - 1]?.[0] as Record<string, unknown>;
}

describe('el toggle no ofrece un cuarto preset', () => {
  /*
   * PHASE-47 — aquí había dos casos sobre cuándo aparecía el chip «Mi ciclo».
   * El chip ya no existe: el día que el usuario declara en Ajustes no añade
   * una opción al toggle, REDEFINE qué significa «Mes».
   */
  it('con ajuste, «Mes» ya es el mes del usuario y no hay chip aparte', () => {
    jest.spyOn(debtApi, 'categorySummary').mockRejectedValue(new Error('sin red'));

    const { getByText, queryByText } = renderScreen(USER_WITH_CYCLE);

    expect(getByText('Mes')).toBeTruthy();
    expect(queryByText(CYCLE_PRESET_LABEL)).toBeNull();

    // Y sin ajuste, exactamente lo mismo: el toggle no cambia de forma según
    // el perfil, sólo cambia lo que «Mes» significa.
    const sinAjuste = renderScreen(USER_WITHOUT_CYCLE);
    expect(sinAjuste.getByText('Mes')).toBeTruthy();
    expect(sinAjuste.queryByText(CYCLE_PRESET_LABEL)).toBeNull();
  });
});

describe('paridad: el ciclo viaja a la API con los bounds de la capa compartida', () => {
  it('manda `range=custom` con los días del ciclo, nunca `range=cycle`', async () => {
    const spy = jest
      .spyOn(debtApi, 'categorySummary')
      .mockRejectedValue(new Error('sin red'));
    const { getByText } = renderScreen(USER_WITH_CYCLE);

    fireEvent.press(getByText('Mes'));

    // El ancla por defecto es el mes en curso, así que el esperado se DERIVA de
    // la misma capa compartida (`currentMonthAnchor` + `cycleDaysForAnchor`) en
    // vez de escribir dos fechas fijas: un literal haría que el test dependiera
    // del mes en que se ejecuta (la bomba de relojería de [AUDIT-2026-08]) y,
    // peor, dejaría de comparar contra la aritmética que usa web.
    // La pantalla reancla al período EN CURSO al pulsar «Mes», y con corte el
    // 14 ése no es el mes de calendario: del 1 al 13 es el que abrió el mes
    // anterior. Se deriva de la misma capa compartida en vez de escribirlo.
    const anclaEnCurso = cycleAnchorContaining(todayDayStr(), 14);
    const expected = cycleDaysForAnchor(14, anclaEnCurso);

    await waitFor(() => {
      const call = lastSummaryCall(spy);
      expect(call).toMatchObject({
        range: 'custom',
        date_from: expected.fromDay,
        date_to: expected.toDay,
      });
    });
    expect(lastSummaryCall(spy).range).not.toBe('cycle');
  });
});

describe('las etiquetas nombran el ciclo, no el mes natural', () => {
  it('el titular nombra el período por el mes que lo ABRE', async () => {
    jest.spyOn(debtApi, 'categorySummary').mockRejectedValue(new Error('sin red'));
    const { getByText, findByText } = renderScreen(USER_WITH_CYCLE);

    fireEvent.press(getByText('Mes'));

    // Decisión del usuario: su mes se llama como siempre se ha llamado, así
    // que el titular sale de `periodLabel` y no de un vocabulario aparte.
    // Derivado de la capa compartida, no escrito a mano: es la MISMA función
    // que titula en web (lección PHASE-44.13).
    const anclaEnCurso = cycleAnchorContaining(todayDayStr(), 14);
    expect(
      await findByText(`Pagos a deuda — ${periodLabel('month', anclaEnCurso)}`),
    ).toBeTruthy();
  });
});

describe('la serie que se pinta depende de lo que el backend puede calcular', () => {
  it('con el mes del usuario se pinta la serie MENSUAL, no la diaria vacía', async () => {
    /*
     * PHASE-47 — la regresión de un bug que se introdujo y se cazó el mismo
     * día. La serie DIARIA sólo la calcula el backend con `range=month`, pero
     * un mes con corte propio viaja como `range=custom` (la API de deuda no
     * tiene parámetro de ciclo). Al hacer que «Mes» fuera el mes del usuario,
     * la condición del render seguía mirando el período de PANTALLA, así que
     * pedía `custom` y pintaba el chart diario — vacío, sin error y sin que
     * nada lo dijera.
     *
     * La condición mira ahora `apiRange`, que es lo que de verdad determina
     * qué devuelve el servidor.
     */
    jest.spyOn(debtApi, 'categorySummary').mockRejectedValue(new Error('sin red'));
    const { getByText, queryByText, findByText } = renderScreen(USER_WITH_CYCLE);

    fireEvent.press(getByText('Mes'));

    expect(await findByText('Evolución mensual')).toBeTruthy();
    expect(queryByText('Evolución de deuda')).toBeNull();
  });

  it('sin día declarado, «Mes» sí trae la serie diaria', async () => {
    // El contrapunto: sin este caso, el de arriba pasaría igual con la serie
    // diaria rota para todo el mundo.
    jest.spyOn(debtApi, 'categorySummary').mockRejectedValue(new Error('sin red'));
    const { getByText, findByText } = renderScreen(USER_WITHOUT_CYCLE);

    fireEvent.press(getByText('Mes'));

    expect(await findByText('Evolución de deuda')).toBeTruthy();
  });
});

describe('ya no queda nada cortando por mes natural en esta pantalla', () => {
  it('sin aviso, porque la serie mensual corta por el mismo período que todo', async () => {
    /*
     * PHASE-47 — aquí se comprobaba que apareciera el aviso «esta tarjeta
     * cuenta el mes de siempre». Existía porque la serie mensual de deuda
     * cortaba por calendario mientras el resto de la pantalla cortaba por el
     * mes del usuario: una diferencia deliberada que, sin nombrarla, se lee
     * como un fallo.
     *
     * Ya no hay diferencia que nombrar. El test se invierte en vez de
     * borrarse: si alguien devolviera la serie al mes natural sin reponer el
     * aviso, esto seguiría en verde y el usuario volvería a ver dos cifras del
     * mismo dinero sin explicación — así que lo que se afirma ahora es que la
     * pantalla NO tiene nada que explicar.
     */
    jest.spyOn(debtApi, 'categorySummary').mockRejectedValue(new Error('sin red'));
    const { getByText, queryByText } = renderScreen(USER_WITH_CYCLE);

    fireEvent.press(getByText('Mes'));

    expect(queryByText(NATURAL_MONTH_NOTICE)).toBeNull();
  });
});
