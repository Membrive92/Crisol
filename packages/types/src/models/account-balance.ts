/**
 * Tipos del agregado de saldo por cuenta (PHASE-19.4).
 */

import type { AccountNature, AccountType } from './account';

export interface AccountBalance {
  account_id: string;
  name: string;
  type: AccountType;
  nature: AccountNature;
  currency: string;
  color: string | null;
  icon: string | null;
  /** Decimal serializado como string. */
  opening_balance: string;
  /** Suma neta de movimientos en la moneda nativa de la cuenta. */
  movements_balance: string;
  /** `opening_balance + movements_balance`. */
  current_balance: string;
  /**
   * PHASE-31.4 — `true` para cuentas que NO entran al agregado de
   * patrimonio (brokerage / crypto, hasta que exista módulo de
   * inversión real). Siguen visibles y siguen siendo destino válido
   * de transferencias.
   */
  is_unvalued?: boolean;
  /**
   * PHASE-35 — Tarjeta padre si esta cuenta es una compra a plazos. NULL en
   * cuentas normales. La vista de deuda agrupa las hijas bajo su tarjeta.
   */
  parent_account_id?: string | null;
}

export interface AccountBalancesResponse {
  items: AccountBalance[];
  total_assets: string;
  total_liabilities: string;
  net_worth: string;
  /** True si las cuentas activas no comparten moneda — los totales son suma cruda. */
  mixed_currencies: boolean;
  reference_currency: string;
}
