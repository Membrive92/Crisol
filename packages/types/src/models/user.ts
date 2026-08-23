export interface User {
  id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  /**
   * C2 (ciclo definido por el usuario) — Día en que empieza SU mes a efectos de
   * PRESENTACIÓN (1–28). `null` = mes natural, que es el estado de todo el
   * mundo hasta que lo cambia.
   *
   * **Opcional a propósito, y esto no es una floritura del tipo**: mientras
   * exista un backend en marcha anterior a la columna, el campo no viaja en
   * `GET /auth/me` y llega AUSENTE. Con el campo declarado obligatorio, `tsc`
   * bendice `user.cycle_start_day !== null`, que es `true` para `undefined` —
   * o sea, la app trataría a TODO el mundo como si tuviera un ciclo
   * configurado (lección PHASE-47.E, donde la misma comparación pintó un
   * asterisco de "gasto aplazado" en cada fila de la lista).
   *
   * Regla de uso, sin excepciones: guarda por VERDAD
   * (`user.cycle_start_day ? … : …`) o, mejor, por
   * `isValidCycleStartDay(...)` de `@crisol/services`, que además rechaza 0,
   * 29 y los no-enteros por la misma puerta. Nunca comparando con `null`.
   */
  cycle_start_day?: number | null;
  created_at: string;
  updated_at: string;
}
