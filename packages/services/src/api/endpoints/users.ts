import type { UpdateMeRequest, User } from '@crisol/types';

import { apiClient } from '../client';

/**
 * C2 (ciclo definido por el usuario) — Escritura del perfil autenticado.
 *
 * La LECTURA vive en `authApi.getMe()` (`GET /auth/me`), que ya devuelve el
 * mismo `UserResponse`. Aquí NO se añade un `getMe` espejo a propósito: dos
 * rutas para el mismo dato acaban siendo dos formas distintas de la misma
 * respuesta, y el backend tomó esa decisión primero (`users/router.py` lo dice
 * en su docstring de módulo).
 */
export const usersApi = {
  /**
   * Actualiza las preferencias del usuario autenticado y devuelve el perfil
   * completo ya actualizado.
   *
   * `cycle_start_day` viaja SIEMPRE: `null` significa «vuelve al mes natural»,
   * no «no lo toques». Fuera de 1–28 el backend responde 422.
   */
  async updateMe(data: UpdateMeRequest): Promise<User> {
    const response = await apiClient.patch<User>('/users/me', data);
    return response.data;
  },
};
