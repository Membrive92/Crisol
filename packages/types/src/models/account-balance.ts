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
