import type { AccountType } from '../models/account';

export interface AccountCreateRequest {
  name: string;
  type: AccountType;
  currency?: string;
  color?: string | null;
  icon?: string | null;
  opening_balance?: string;
  opening_balance_date?: string | null;
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
  display_order?: number;
  is_archived?: boolean;
}
