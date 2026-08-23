import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { UpdateMeRequest, User } from '@crisol/types';

import { authApi } from '../../api/endpoints/auth';
import { usersApi } from '../../api/endpoints/users';
import { queryKeys } from '../keys';

/**
 * C2 (ciclo definido por el usuario) — Lectura REACTIVA del perfil.
 *
 * `queryKeys.auth.me` llevaba declarada desde siempre **sin un solo
 * consumidor**: el perfil se pedía imperativamente (`authApi.getMe()` desde
 * login y desde el layout) y vivía en `useAuthStore`. Con un dato de perfil que
 * la propia app puede cambiar —el día en que empieza tu mes— hace falta que una
 * pantalla pueda leerlo y verlo cambiar sin recargar; eso es una query, no una
 * lectura de arranque.
 *
 * `staleTime` alto a propósito: el perfil sólo cambia porque el usuario lo
 * cambia, y esa mutación invalida la key.
 */
export function useMe() {
  return useQuery<User, Error>({
    queryKey: queryKeys.auth.me,
    queryFn: () => authApi.getMe(),
    staleTime: 1000 * 60 * 5,
  });
}

/**
 * Guarda las preferencias del perfil (`PATCH /users/me`).
 *
 * ⚠️ **Sincroniza tú el store de sesión.** Este hook invalida
 * `queryKeys.auth.me`, pero NO toca `useAuthStore`: `@crisol/services` no
 * depende de `@crisol/store` —lo dice la regla de imports de
 * `architecture.md`, y se retiró expresamente esa dependencia en AUDIT-2026-05
 * (misma nota en `useTransactions`)—, así que el paquete no puede importarlo
 * aunque quisiera. Y la mitad del frontend lee el usuario del STORE, no de la
 * query: invalidar sólo la key dejaría a esas pantallas con el valor viejo
 * hasta el siguiente login.
 *
 * El llamante cierra el círculo en su propio `onSuccess`, que TanStack ejecuta
 * DESPUÉS de éste:
 *
 * ```ts
 * update.mutate(
 *   { cycle_start_day: 14 },
 *   { onSuccess: (updated) => useAuthStore.getState().setUser(updated) },
 * );
 * ```
 *
 * Devolver el `User` completo desde el endpoint (y no un 204) existe justo para
 * eso: el llamante no tiene que reconstruir el objeto ni volver a pedirlo.
 */
export function useUpdateMe() {
  const queryClient = useQueryClient();
  return useMutation<User, Error, UpdateMeRequest>({
    mutationFn: (data) => usersApi.updateMe(data),
    onSuccess: (updated) => {
      // `setQueryData` antes de invalidar: la respuesta YA es el perfil nuevo,
      // así que la pantalla no tiene por qué parpadear con el valor viejo
      // mientras vuelve el refetch.
      queryClient.setQueryData(queryKeys.auth.me, updated);
      void queryClient.invalidateQueries({ queryKey: queryKeys.auth.me });
    },
  });
}
