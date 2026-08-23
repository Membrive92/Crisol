// @types/jest expone los globals (describe/it/expect) — sin import.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, waitFor } from '@testing-library/react-native';
import type { ReactNode } from 'react';

import {
  currentMonthAnchor,
  cycleAnchorContaining,
  cycleBoundsForAnchor,
  dashboardApi,
  queryKeys,
  todayDayStr,
} from '@crisol/services';
import type { User } from '@crisol/types';
import { CYCLE_PRESET_LABEL, NATURAL_MONTH_NOTICE } from '@crisol/ui';

/*
 * Charts y router sustituidos: `react-native-gifted-charts` arrastra un
 * paquete ESM que el `transformIgnorePatterns` de la app no transforma, y
 * `expo-router` exige un contenedor de navegación. Ninguno de los dos
 * interviene en lo que se comprueba aquí.
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

import AnalysisScreen from './analysis';

/*
 * C3a / C4 — El preset «Mi ciclo» en la pantalla de Análisis (móvil).
 *
 * Dos cosas se fijan aquí, y las dos son de PARIDAD con web:
 *
 * 1. Los BOUNDS. Esta pantalla no guarda ancla —enseña siempre «ahora»—, así
 *    que el ciclo en curso se deriva del día de hoy. Con D=14, el 5 de agosto
 *    el usuario sigue dentro del ciclo que abrió el 14 de julio: usar el mes en
 *    curso como ancla pintaría un ciclo que aún no ha empezado.
 * 2. El `cycle: true` de las queries. El día NO viaja del cliente; lo lee el
 *    servidor del perfil. Sin el flag, el backend bucketea por mes natural y la
 *    pantalla enseñaría el mes de siempre bajo el rótulo del ciclo.
 */

const CYCLE_DAY = 14;

/*
 * Reloj CONGELADO en el 5 de agosto — y no es comodidad, es la única forma de
 * que este fichero distinga lo que dice medir.
 *
 * La pantalla deriva el ciclo EN CURSO del día de hoy. Con hoy ≥ D (14) ese
 * ciclo abre este mismo mes, así que `cycleAnchorContaining(hoy)` y «el mes en
 * curso» dan LO MISMO y anclar mal pasa desapercibido la mitad de los días del
 * mes. Comprobado rompiendo el código: con el reloj real (día 20), sustituir la
 * derivación del ancla por `monthAnchor` no tumbaba NI UN test.
 *
 * Se falsea SÓLO `Date`: `doNotFake` deja los temporizadores reales, para que
 * `waitFor` y TanStack Query sigan corriendo con timers de verdad.
 */
const FROZEN_NOW = new Date('2026-08-05T12:00:00.000Z');
const KEEP_REAL = [
  'hrtime',
  'nextTick',
  'performance',
  'queueMicrotask',
  'requestAnimationFrame',
  'cancelAnimationFrame',
  'requestIdleCallback',
  'cancelIdleCallback',
  'setImmediate',
  'clearImmediate',
  'setInterval',
  'clearInterval',
  'setTimeout',
  'clearTimeout',
] as const;

beforeEach(() => {
  jest.useFakeTimers({ doNotFake: [...KEEP_REAL] });
  jest.setSystemTime(FROZEN_NOW);
});

afterEach(() => {
  jest.useRealTimers();
});

const USER_WITH_CYCLE: User = {
  id: 'u-1',
  email: 'test@example.com',
  display_name: 'Test',
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  cycle_start_day: CYCLE_DAY,
};

/**
 * Perfil de un backend ANTERIOR a la columna: la clave va OMITIDA, no puesta a
 * `null`. Con `null` el test pasaría igual y no probaría nada — el fallo que
 * existe para cazar es `undefined !== null`, que es cierto (lección PHASE-47.E).
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
      <AnalysisScreen />
    </QueryClientProvider>,
  );
}

/**
 * Ninguna query debe salir a la red: lo que se mide es CON QUÉ se piden, no qué
 * devuelven. Todas fallan a propósito y la pantalla queda en su estado de
 * error, que es suficiente para leer los parámetros.
 */
function stubDashboard() {
  const fail = () => new Error('sin red');
  const summary = jest.spyOn(dashboardApi, 'summary').mockRejectedValue(fail());
  const byMonth = jest.spyOn(dashboardApi, 'byMonth').mockRejectedValue(fail());
  jest.spyOn(dashboardApi, 'byCategory').mockRejectedValue(fail());
  jest.spyOn(dashboardApi, 'topExpenses').mockRejectedValue(fail());
  jest.spyOn(dashboardApi, 'currencies').mockRejectedValue(fail());
  return { summary, byMonth };
}

function lastCall(spy: jest.SpyInstance): Record<string, unknown> {
  const calls = spy.mock.calls;
  return calls[calls.length - 1]?.[0] as Record<string, unknown>;
}

describe('el toggle no ofrece un cuarto preset', () => {
  /*
   * PHASE-47 — el chip «Mi ciclo» ya no existe. El día declarado en Ajustes
   * REDEFINE qué significa «Mes» en vez de añadir una opción al toggle.
   */
  it('con ajuste, «Mes» ya es el mes del usuario y no hay chip aparte', () => {
    stubDashboard();

    const { getByText, queryByText } = renderScreen(USER_WITH_CYCLE);

    expect(getByText('Mes')).toBeTruthy();
    expect(queryByText(CYCLE_PRESET_LABEL)).toBeNull();
  });
});

describe('paridad: los bounds del ciclo salen de la capa compartida', () => {
  it('el resumen se pide con el rango del ciclo EN CURSO y con `cycle: true`', async () => {
    const spies = stubDashboard();
    const { getByText } = renderScreen(USER_WITH_CYCLE);

    fireEvent.press(getByText('Mes'));

    // Esperado DERIVADO de la capa compartida —la misma que usa web—, no dos
    // ISO escritos a mano: un literal dependería del día en que se ejecute el
    // test (bomba de relojería de [AUDIT-2026-08]) y dejaría de comparar contra
    // la aritmética real. `cycleAnchorContaining(hoy)` es la pieza que impide
    // que la pantalla ancle el ciclo en el mes en curso.
    const cycleAnchor = cycleAnchorContaining(todayDayStr(), CYCLE_DAY);
    const expected = cycleBoundsForAnchor(CYCLE_DAY, cycleAnchor);

    // Guarda del propio test: si el escenario no distingue el ancla del ciclo
    // del mes en curso, lo de abajo pasaría con la pantalla anclando mal. Es la
    // afirmación que faltaba cuando el reloj real (día 20) hacía que las dos
    // coincidieran.
    expect(cycleAnchor).not.toBe(currentMonthAnchor());

    await waitFor(() => {
      expect(lastCall(spies.summary)).toMatchObject({
        date_from: expected.dateFrom,
        date_to: expected.dateTo,
        cycle: true,
      });
    });
  });

  it('la serie de barras pide el AÑO del ciclo con `cycle: true`', async () => {
    // C4 — el histórico entero en barras de ciclo, no sólo el ciclo navegado:
    // el backend devuelve los 12 ciclos que ABREN en ese año.
    const spies = stubDashboard();
    const { getByText } = renderScreen(USER_WITH_CYCLE);

    fireEvent.press(getByText('Mes'));

    const expectedYear = Number(
      cycleAnchorContaining(todayDayStr(), CYCLE_DAY).slice(0, 4),
    );

    await waitFor(() => {
      expect(lastCall(spies.byMonth)).toMatchObject({
        year: expectedYear,
        cycle: true,
      });
    });
  });

  it('sin día declarado, ninguna query lleva `cycle`', async () => {
    /*
     * PHASE-47 — este test decía lo contrario y hay que decirlo en voz alta:
     * afirmaba que un usuario CON ajuste no mandaba `cycle` hasta pulsar el
     * chip. Esa era justo la dualidad que el usuario pidió quitar — el ajuste
     * existía y la pantalla seguía enseñándole el mes natural.
     *
     * Lo que sobrevive es la mitad que importa: quien no ha configurado nada
     * no puede ver sus datos recortados por un flag que nadie pidió.
     */
    const spies = stubDashboard();
    renderScreen(USER_WITHOUT_CYCLE);

    await waitFor(() => expect(spies.summary).toHaveBeenCalled());
    expect(lastCall(spies.summary).cycle).toBeUndefined();
    expect(lastCall(spies.byMonth).cycle).toBeUndefined();
  });

  it('con día declarado, el flag viaja SIN que el usuario pulse nada', async () => {
    // La otra mitad, y la que el rediseño estrena: el ajuste manda desde el
    // primer render. Sin este caso, el anterior pasaría igual con la feature
    // entera apagada.
    const spies = stubDashboard();
    renderScreen(USER_WITH_CYCLE);

    await waitFor(() => expect(spies.summary).toHaveBeenCalled());
    expect(lastCall(spies.summary).cycle).toBe(true);
  });
});

describe('lo que sigue en mes natural lo dice', () => {
  it('las tarjetas que no cortan por el mes del usuario llevan el aviso', async () => {
    stubDashboard();
    const { findAllByText } = renderScreen(USER_WITH_CYCLE);

    /*
     * PHASE-47 — sin pulsar nada. Antes había que activar el preset para que
     * el aviso apareciera; ahora lo dispara el PERFIL, y eso es precisamente
     * lo que hay que probar: quien declaró su día ve el descuadre explicado
     * desde el primer render, sin haber elegido nada en esta pantalla.
     *
     * UNO: la evolución de patrimonio, cuya serie son 12 meses de calendario
     * fijos. Eran tres, y los otros dos MENTÍAN: la proyección de fin de mes y
     * los insights se migraron al mes del usuario en la misma entrega, así que
     * el aviso afirmaba lo contrario de lo que hacía el código y este test
     * cementaba la mentira exigiendo que siguieran ahí.
     *
     * La redacción es la ÚNICA de `@crisol/ui`; escrita a mano en cada sitio,
     * divergiría.
     */
    expect(await findAllByText(NATURAL_MONTH_NOTICE)).toHaveLength(1);
  });
});
