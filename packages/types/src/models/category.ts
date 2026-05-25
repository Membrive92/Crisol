export type CategoryKind = 'income' | 'expense';

/**
 * PHASE-30.1 — Rol semántico de la categoría dentro del producto.
 *
 * Sustituye al hardcoded `INTEREST_CATEGORY_NAMES` del backend y absorbe
 * `is_transfer` en un único atributo declarativo. Los consumidores que
 * necesitan "todas las categorías de deuda" filtran por
 * `role === 'DEBT_PAYMENT' || role === 'DEBT_INTEREST'`.
 *
 * Mientras el módulo de deuda en dos capas (PHASE-30) está en desarrollo
 * `is_transfer` se mantiene en la entidad por compatibilidad.
 */
export type CategoryRole =
  | 'GENERIC'
  | 'TRANSFER'
  | 'DEBT_PAYMENT'
  | 'DEBT_INTEREST';

export interface Category {
  id: string;
  user_id: string;
  name: string;
  icon: string | null;
  color: string | null;
  kind: CategoryKind;
  /**
   * PHASE-23.1: si `true`, las txs con esta categoría son transferencias
   * internas y quedan fuera del cashflow agregado (dashboard,
   * presupuestos), pero SIGUEN contribuyendo al saldo de la cuenta con
   * el signo dictado por `kind`. Separa "es transferencia" del "signo
   * en balance" — corrige el bug de PHASE-23 que rompía saldos.
   */
  is_transfer: boolean;
  /**
   * PHASE-30.1 — Rol semántico (ver `CategoryRole`). Las nuevas filas
   * por defecto reciben `GENERIC`; el seed declara `TRANSFER`,
   * `DEBT_PAYMENT` y `DEBT_INTEREST` en las categorías relevantes.
   */
  role: CategoryRole;
  created_at: string;
  updated_at: string;
}
