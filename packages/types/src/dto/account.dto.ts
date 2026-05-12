import type { AccountType } from '../models/account';

export interface AccountCreateRequest {
  name: string;
  type: AccountType;
  currency?: string;
  color?: string | null;
  icon?: string | null;
  opening_balance?: string;
  opening_balance_date?: string | null;
  /** PHASE-22.3: APR anual decimal. Sólo loan/mortgage. */
  apr?: string | null;
  /** Plazo total en meses. Sólo loan/mortgage. */
  term_months?: number | null;
  start_date?: string | null;
  display_order?: number;
}

export interface AccountUpdateRequest {
  name?: string;
  type?: AccountType;
  currency?: string;
  color?: string | null;
  icon?: string | null;
  opening_balance?: string;
  opening_balance_date?: string | null;
  apr?: string | null;
  term_months?: number | null;
  start_date?: string | null;
  display_order?: number;
  is_archived?: boolean;
}
