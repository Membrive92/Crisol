import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from '../client';
import { usersApi } from './users';

describe('usersApi.updateMe', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('hace PATCH a /users/me con el día del ciclo', async () => {
    const spy = vi
      .spyOn(apiClient, 'patch')
      .mockResolvedValue({ data: { id: 'u-1', cycle_start_day: 14 } });

    await usersApi.updateMe({ cycle_start_day: 14 });

    expect(spy).toHaveBeenCalledWith('/users/me', { cycle_start_day: 14 });
  });

  /*
   * «Volver al mes natural» viaja como `null` EXPLÍCITO, no omitiendo la clave.
   * Si se omitiera, el backend no podría distinguir «no lo toques» de «bórralo»
   * — y ese tri-estado es justo lo que el contrato evita declarando el campo
   * requerido en el body. Con un `{}` por medio, el ajuste sería
   * inquitable desde la UI.
   */
  it('«volver al mes natural» manda null explícito, no un body vacío', async () => {
    const spy = vi
      .spyOn(apiClient, 'patch')
      .mockResolvedValue({ data: { id: 'u-1', cycle_start_day: null } });

    await usersApi.updateMe({ cycle_start_day: null });

    // `toStrictEqual` y no `toEqual`: el segundo da por buena una clave con
    // `undefined`, que es exactamente el estado que este test descarta.
    expect(spy.mock.calls[0]?.[1]).toStrictEqual({ cycle_start_day: null });
  });
});
