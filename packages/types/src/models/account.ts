/**
 * Tipos del dominio de cuentas (PHASE-19.1).
 *
 * Mantén el enum sincronizado con `backend/.../accounts/models.py`.
 * Los `liability` (`credit_card`, `loan`, `mortgage`) están reservados
 * para PHASE-20 — el frontend de PHASE-19.1 sólo expone los `asset`.
 */

export type AccountType =
  | 'bank'
  | 'savings'
  | 'brokerage'
  | 'crypto'
  | 'cash'
  | 'credit_card'
  | 'loan'
  | 'mortgage';

export type AccountNature = 'asset' | 'liability';

/** Tipos `asset` que la UI permite crear / editar en PHASE-19.1. */
export const ASSET_ACCOUNT_TYPES: readonly AccountType[] = [
  'bank',
  'savings',
  'brokerage',
  'crypto',
  'cash',
] as const;

export interface Account {
  id: string;
  user_id: string;
  name: string;
  type: AccountType;
  nature: AccountNature;
  currency: string;
  color: string | null;
  icon: string | null;
  /** Decimal serializado como string. */
  opening_balance: string;
  /** YYYY-MM-DD o null. */
  opening_balance_date: string | null;
  display_order: number;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
}
