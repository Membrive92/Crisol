/**
 * C2 (ciclo definido por el usuario) — Body de `PATCH /users/me`.
 *
 * Es la primera preferencia de perfil del sistema, así que aquí se fija la
 * convención con la que nacerán las siguientes.
 */

/**
 * Preferencias del perfil autenticado. Hoy sólo el ciclo del usuario.
 *
 * `cycle_start_day` es **requerido en el body** aunque acepte `null`: mandar
 * `null` significa «vuelvo al mes natural». Espeja al backend
 * (`users/schemas.py::UserUpdate`), que lo declara igual y por el mismo motivo:
 * un campo opcional-y-nullable obliga a distinguir ausente-vs-`null`, que es el
 * tri-estado que convierte un PATCH en una fuente de ambigüedad. No hay
 * `id` de usuario: el único perfil que el endpoint puede tocar es el del token.
 */
export interface UpdateMeRequest {
  /** Día que abre el mes del usuario (1–28), o `null` para el mes natural. */
  cycle_start_day: number | null;
}
