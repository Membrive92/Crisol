// @types/jest expone los globals (describe/it/expect/jest) — sin import.
import { act, fireEvent, render } from '@testing-library/react-native';

import type * as ReactModule from 'react';
import type * as ReactNativeModule from 'react-native';

import type * as ServicesModule from '@crisol/services';
import { useAuthStore } from '@crisol/store';
import type { UpdateMeRequest, User } from '@crisol/types';

/*
 * C2 (móvil, decisión D4 del plan) — El ajuste del día en que empieza el mes.
 *
 * Tres cosas que se pueden romper en silencio y que aquí quedan atadas:
 *
 *  1. Que el selector ofrezca un día que la aritmética no admite (29–31
 *     obligarían a clampar en febrero, y el clamp es una charca de bugs).
 *  2. Que la pantalla trate como «ciclo configurado» a un usuario cuyo perfil
 *     llega SIN la clave — el caso real mientras exista un backend anterior a
 *     la columna. Es la lección [PHASE-47.E] literal: `undefined !== null` es
 *     `true`, así que una comparación estricta da por configurado a todo el
 *     mundo. El fixture OMITE la clave; ponerla a `null` haría pasar el test
 *     igual y no probaría nada.
 *  3. Que «volver al mes natural» mande otra cosa que `null`.
 */

interface MeResult {
  data: User | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
}

const mockMutate = jest.fn();
const mockMeState: { value: MeResult } = {
  value: { data: undefined, isLoading: false, isError: false, error: null },
};

jest.mock('@crisol/services', () => {
  const actual = jest.requireActual<typeof ServicesModule>('@crisol/services');
  return {
    ...actual,
    useMe: () => mockMeState.value,
    useUpdateMe: () => ({ mutate: mockMutate, isPending: false }),
  };
});

// La previsualización tiene su propio test (`cycle-preview.test.tsx`); aquí
// sólo interesa SI se monta y con qué día. Sin JSX dentro de la factoría: el
// hoisting de `jest.mock` la coloca por encima de los imports del fichero.
jest.mock('./cycle-preview', () => {
  const React = jest.requireActual<typeof ReactModule>('react');
  const RN = jest.requireActual<typeof ReactNativeModule>('react-native');
  return {
    CyclePreview: ({ cycleStartDay }: { cycleStartDay: number }) =>
      React.createElement(RN.Text, { testID: 'preview' }, `preview:${cycleStartDay}`),
  };
});

import { CycleSettings } from './cycle-settings';

/**
 * Usuario base SIN `cycle_start_day`: es la forma que devuelve un backend
 * anterior a la columna, y la que el tipo declara posible.
 */
function user(over: Partial<User> = {}): User {
  return {
    id: 'u-1',
    email: 'membrij7@example.com',
    display_name: 'Membrive',
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...over,
  };
}

function renderWith(data: User | undefined) {
  mockMeState.value = { data, isLoading: false, isError: false, error: null };
  return render(<CycleSettings />);
}

beforeEach(() => {
  mockMutate.mockClear();
});

describe('CycleSettings (móvil) · el selector', () => {
  it('ofrece los días 1 a 28 y ninguno más, además del mes natural', () => {
    const { getAllByTestId, getByTestId, queryByLabelText } = renderWith(
      user({ cycle_start_day: null }),
    );

    // La opción que devuelve al mes natural existe y es distinta de los días.
    expect(getByTestId('cycle-default-mode')).toBeTruthy();

    fireEvent(getByTestId('cycle-default-mode'), 'valueChange', false);
    expect(getAllByTestId('cycle-day-option')).toHaveLength(28);
    expect(queryByLabelText('Día 1')).toBeTruthy();
    expect(queryByLabelText('Día 28')).toBeTruthy();
    expect(queryByLabelText('Día 0')).toBeNull();
    expect(queryByLabelText('Día 29')).toBeNull();
  });
});

describe('CycleSettings (móvil) · el campo que NO llega', () => {
  it('con la clave OMITIDA trata al usuario como mes natural', () => {
    const { getByText, queryByText, queryByTestId } = renderWith(user());

    expect(getByText(/estás en modo predeterminado/i)).toBeTruthy();
    expect(queryByText(/tu mes empieza el día/i)).toBeNull();
    expect(queryByTestId('preview')).toBeNull();
  });

  /*
   * El contrapunto del test de arriba: sin éste, «no hay previsualización»
   * podría estar pasando porque la previsualización no se monta NUNCA, y el
   * caso ausente no probaría nada.
   */
  it('con el día guardado sí enseña el estado y la previsualización', () => {
    const { getByText, queryByText, getByTestId } = renderWith(user({ cycle_start_day: 14 }));

    expect(getByText(/tu mes empieza el día 14/i)).toBeTruthy();
    expect(queryByText(/estás en modo predeterminado/i)).toBeNull();
    expect(getByTestId('preview')).toHaveTextContent('preview:14');
  });
});

describe('CycleSettings (móvil) · guardar', () => {
  it('manda el día elegido', () => {
    const { getByLabelText, getByTestId } = renderWith(user({ cycle_start_day: null }));

    // La rejilla de días sólo existe con el modo predeterminado apagado.

    fireEvent(getByTestId('cycle-default-mode'), 'valueChange', false);

    fireEvent.press(getByLabelText('Día 14'));
    fireEvent.press(getByTestId('cycle-save'));

    expect(mockMutate).toHaveBeenCalledTimes(1);
    const payload: UpdateMeRequest | undefined = mockMutate.mock.calls[0]?.[0];
    expect(payload).toEqual({ cycle_start_day: 14 });
  });

  it('«volver al mes natural» manda null, no un body vacío', () => {
    const { getByTestId } = renderWith(user({ cycle_start_day: 14 }));

    fireEvent(getByTestId('cycle-default-mode'), 'valueChange', true);
    fireEvent.press(getByTestId('cycle-save'));

    expect(mockMutate).toHaveBeenCalledTimes(1);
    // `toStrictEqual`: `toEqual` daría por bueno un `undefined`, que es
    // exactamente el estado que este test descarta.
    expect(mockMutate.mock.calls[0]?.[0]).toStrictEqual({ cycle_start_day: null });
  });

  it('sin cambios el botón no se puede pulsar', () => {
    const { getByTestId } = renderWith(user({ cycle_start_day: 14 }));

    const save = getByTestId('cycle-save');
    expect(save.props.accessibilityState?.disabled).toBe(true);
    fireEvent.press(save);
    expect(mockMutate).not.toHaveBeenCalled();
  });

  it('elegir un día previsualiza ANTES de guardar', () => {
    const { getByLabelText, getByTestId, queryByTestId } = renderWith(
      user({ cycle_start_day: null }),
    );

    expect(queryByTestId('preview')).toBeNull();
    // La rejilla de días sólo existe con el modo predeterminado apagado.
    fireEvent(getByTestId('cycle-default-mode'), 'valueChange', false);
    fireEvent.press(getByLabelText('Día 20'));

    expect(getByTestId('preview')).toHaveTextContent('preview:20');
    expect(mockMutate).not.toHaveBeenCalled();
  });
});

describe('CycleSettings (móvil) · lo que la pantalla promete por escrito', () => {
  it('avisa de que cambiar el día re-corta TODO el histórico y cambia la base de las comparativas', () => {
    // Es la decisión D2 del plan, y es una promesa de honestidad: sin este
    // aviso el usuario ve moverse cifras de hace un año sin explicación, que es
    // justo el «no me cuadra» que esta fase existe para matar.
    const { getByText } = renderWith(user({ cycle_start_day: 14 }));

    expect(getByText(/todo tu histórico/i)).toBeTruthy();
    expect(getByText(/período anterior/i)).toBeTruthy();
    expect(getByText(/no se mueve ni un céntimo/i)).toBeTruthy();
  });

  it('tras guardar, sincroniza el perfil que lee el resto de la app', () => {
    // Hay DOS fuentes del usuario: la query `auth.me` (que invalida el hook) y
    // el store de Zustand, que es de donde leen las demás pantallas. Si esta
    // línea se pierde en un refactor, el chip «Mi ciclo» no aparecería en
    // ninguna otra pantalla hasta el próximo login — el layout sólo pide el
    // perfil cuando el store está vacío.
    const { getByLabelText, getByTestId } = renderWith(user({ cycle_start_day: null }));

    // El `onSuccess` viaja en la llamada a `mutate`, no en el hook. Con un
    // `jest.fn()` pelado nadie lo invoca nunca, así que TODO su cuerpo
    // (sincronizar el store, limpiar el borrador, el toast) sería código que no
    // ejecuta ningún test: borrar la línea del `setUser` dejaría la suite
    // entera en verde.
    // La rejilla de días sólo existe con el modo predeterminado apagado.
    fireEvent(getByTestId('cycle-default-mode'), 'valueChange', false);
    fireEvent.press(getByLabelText('Día 14'));
    fireEvent.press(getByTestId('cycle-save'));

    const opciones: { onSuccess?: (u: User) => void } | undefined =
      mockMutate.mock.calls.at(-1)?.[1];
    expect(opciones?.onSuccess).toBeInstanceOf(Function);

    // El `onSuccess` limpia el borrador, así que provoca un render: en `act`
    // para no dejar una actualización de estado fuera del ciclo del test.
    act(() => {
      opciones?.onSuccess?.(user({ cycle_start_day: 14 }));
    });

    expect(useAuthStore.getState().user?.cycle_start_day).toBe(14);
  });
});
