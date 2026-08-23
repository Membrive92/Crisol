import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type * as ServicesModule from '@crisol/services';
import type { UpdateMeRequest, User } from '@crisol/types';

/*
 * C2 — El ajuste del día en que empieza el mes.
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

const mutate = vi.fn();
let meResult: {
  data: User | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
};

vi.mock('@crisol/services', async (importOriginal) => {
  const actual = await importOriginal<typeof ServicesModule>();
  return {
    ...actual,
    useMe: () => meResult,
    useUpdateMe: () => ({ mutate, isPending: false }),
  };
});

// La previsualización tiene su propio test (`cycle-preview.test.tsx`); aquí
// sólo interesa SI se monta y con qué día.
vi.mock('./cycle-preview', () => ({
  CyclePreview: ({ cycleStartDay }: { cycleStartDay: number }) => (
    <div data-testid="preview">preview:{cycleStartDay}</div>
  ),
}));

import { useAuthStore } from '@crisol/store';

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
  meResult = { data, isLoading: false, isError: false, error: null };
  render(<CycleSettings />);
}

function daySelect(): HTMLSelectElement {
  const el = screen.getByLabelText('El día en que empieza tu mes');
  if (!(el instanceof HTMLSelectElement)) {
    throw new Error('El control del día no es un <select>');
  }
  return el;
}

/** El check «Modo predeterminado»: marcado = mes natural (envía `null`). */
function modoPredeterminado(): HTMLInputElement {
  return screen.getByRole('checkbox', { name: /modo predeterminado/i }) as HTMLInputElement;
}

/**
 * Desmarca el modo predeterminado si estaba marcado, que es lo que hace
 * aparecer el desplegable de días. Idempotente para poder llamarlo sin
 * comprobar el estado previo.
 */
async function desmarcarModoPredeterminado(): Promise<void> {
  const check = modoPredeterminado();
  if (check.checked) await userEvent.click(check);
}


beforeEach(() => {
  mutate.mockClear();
});

describe('CycleSettings · el selector', () => {
  it('ofrece los días 1 a 28 y ninguno más — el mes natural ya no es una opción', async () => {
    renderWith(user({ cycle_start_day: null }));

    await desmarcarModoPredeterminado();
    const values = Array.from(daySelect().options).map((o) => o.value);
    // El mes natural salió del desplegable: no es un día de corte, es la
    // AUSENCIA de uno, y ahora lo declara el check «Modo predeterminado».
    // El desplegable ya NO ofrece «mes natural»: eso lo declara el check, y
    // mezclarlos obligaba a leer trece entradas para ver que la primera era de
    // otra naturaleza.
    expect(values).not.toContain('');

    const days = values.map(Number);
    expect(days).toHaveLength(28);
    expect(Math.min(...days)).toBe(1);
    expect(Math.max(...days)).toBe(28);
    expect(days).not.toContain(0);
    expect(days).not.toContain(29);
  });
});

describe('CycleSettings · el campo que NO llega', () => {
  it('con la clave OMITIDA trata al usuario como mes natural', () => {
    renderWith(user());

    expect(screen.getByText(/estás en modo predeterminado/i)).toBeDefined();
    expect(screen.queryByText(/tu mes empieza el día/i)).toBeNull();
    // El check refleja el estado, y el desplegable de días ni siquiera existe:
    // no hay día que elegir mientras el mes sea el natural.
    expect(modoPredeterminado().checked).toBe(true);
    expect(screen.queryByLabelText('El día en que empieza tu mes')).toBeNull();
    expect(screen.queryByTestId('preview')).toBeNull();
  });

  /*
   * El contrapunto del test de arriba: sin éste, «no hay previsualización»
   * podría estar pasando porque la previsualización no se monta NUNCA, y el
   * caso ausente no probaría nada.
   */
  it('con el día guardado sí enseña el estado y la previsualización', () => {
    renderWith(user({ cycle_start_day: 14 }));

    expect(screen.getByText(/tu mes empieza el día 14/i)).toBeDefined();
    expect(screen.queryByText(/estás en modo predeterminado/i)).toBeNull();
    expect(daySelect().value).toBe('14');
    expect(screen.getByTestId('preview').textContent).toBe('preview:14');
  });
});

describe('CycleSettings · guardar', () => {
  it('manda el día elegido', async () => {
    renderWith(user({ cycle_start_day: null }));

    await desmarcarModoPredeterminado();
    await userEvent.selectOptions(daySelect(), '14');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }));

    expect(mutate).toHaveBeenCalledTimes(1);
    const payload: UpdateMeRequest | undefined = mutate.mock.calls[0]?.[0];
    expect(payload).toEqual({ cycle_start_day: 14 });
  });

  it('«volver al mes natural» manda null, no un body vacío', async () => {
    renderWith(user({ cycle_start_day: 14 }));

    await userEvent.click(modoPredeterminado());
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }));

    expect(mutate).toHaveBeenCalledTimes(1);
    // `toStrictEqual`: `toEqual` daría por bueno un `undefined`, que es
    // exactamente el estado que este test descarta.
    expect(mutate.mock.calls[0]?.[0]).toStrictEqual({ cycle_start_day: null });
  });

  it('sin cambios el botón no se puede pulsar', () => {
    renderWith(user({ cycle_start_day: 14 }));

    const button = screen.getByRole('button', { name: 'Guardar' });
    expect(button.hasAttribute('disabled')).toBe(true);
  });

  it('elegir un día previsualiza ANTES de guardar', async () => {
    renderWith(user({ cycle_start_day: null }));

    expect(screen.queryByTestId('preview')).toBeNull();
    await desmarcarModoPredeterminado();
    await userEvent.selectOptions(daySelect(), '20');

    expect(screen.getByTestId('preview').textContent).toBe('preview:20');
    expect(mutate).not.toHaveBeenCalled();
  });
});

/*
 * Regresiones de la revisión adversarial de C2. Las dos cubren código que
 * existía y que ningún test ejecutaba: se comprobó borrándolo y viendo la suite
 * seguir en verde.
 */
describe('lo que la pantalla promete por escrito', () => {
  it('avisa de que cambiar el día re-corta TODO el histórico y cambia la base de las comparativas', () => {
    // Es la decisión D2 del plan, y es una promesa de honestidad: sin este
    // aviso el usuario ve moverse cifras de hace un año sin explicación, que es
    // justo el «no me cuadra» que esta fase existe para matar. El texto estaba;
    // no lo ataba ningún test, así que desaparecía en el próximo retoque de
    // layout sin que nada se quejara.
    renderWith(user({ cycle_start_day: 14 }));

    expect(screen.getByText(/todo tu histórico/i)).toBeTruthy();
    expect(screen.getByText(/período anterior/i)).toBeTruthy();
    expect(screen.getByText(/no se mueve ni un céntimo/i)).toBeTruthy();
  });

  it('tras guardar, sincroniza el perfil que lee el resto de la app', async () => {
    // Hay DOS fuentes del usuario: la query `auth.me` (que invalida el hook) y
    // el store de Zustand, que es de donde leen las demás pantallas. Si esta
    // línea se pierde en un refactor, el chip «Mi ciclo» no aparecería en
    // ninguna otra pantalla hasta el próximo login — el layout sólo pide el
    // perfil cuando el store está vacío.
    renderWith(user({ cycle_start_day: null }));

    // El `onSuccess` viaja en la llamada a `mutate`, no en el hook. Con un
    // `vi.fn()` pelado nadie lo invoca nunca, así que TODO su cuerpo
    // (sincronizar el store, limpiar el borrador, el toast) era código que no
    // ejecutaba ningún test: borrar la línea del `setUser` dejaba la suite
    // entera en verde.
    await desmarcarModoPredeterminado();
    await userEvent.selectOptions(daySelect(), '14');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }));
    const opciones = mutate.mock.calls.at(-1)?.[1] as
      | { onSuccess?: (u: User) => void }
      | undefined;
    expect(opciones?.onSuccess).toBeTypeOf('function');

    const guardado = user({ cycle_start_day: 14 });
    opciones?.onSuccess?.(guardado);

    expect(useAuthStore.getState().user?.cycle_start_day).toBe(14);
  });
});
