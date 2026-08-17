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
   * PHASE-37 — Cuota mensual del cuadro (`installments[0].payment`) para
   * liabilities CON cuadro; `null` para activos y liabilities sin cuadro.
   * La lista de deuda la usa para la "Cuota est." de tarjetas financiadas
   * (cuyo `opening_balance` es 0 y no se puede recomputar en cliente).
   */
  monthly_payment?: string | null;
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
  /**
   * PHASE-47.G — lo que la app calcula MENOS lo que dijo el extracto del banco.
   * `null` si la cuenta nunca se ancló; `"0.00"` es lo normal. Cualquier otra
   * cosa significa que la app y el banco han dejado de coincidir.
   *
   * Opcional a propósito: un backend anterior a 47.G no manda el campo, y
   * comparar con `null` lo daría por presente (lección [PHASE-47.E]).
   */
  statement_gap?: string | null;
  /** PHASE-47.G — tramos de extracto que faltan por importar. */
  statement_seams?: StatementSeam[];
}

/**
 * PHASE-47.G — un tramo que el banco movió y la app no tiene.
 *
 * Sale de la columna Saldo: si el saldo anterior implícito de una fila no
 * aparece en ninguna otra, entre medias hay movimientos sin importar. No da
 * error por sí solo —el anclaje lo absorbe en el saldo inicial—, así que hay
 * que decirlo o no se entera nadie.
 */
export interface StatementSeam {
  after: string;
  before: string;
  /** Cuánto se movió el saldo ahí dentro. Negativo = salió dinero. */
  amount: string;
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
