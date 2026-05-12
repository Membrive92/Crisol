/**
 * Tipos del dominio de cuentas (PHASE-19.1, PHASE-22).
 *
 * Mantén el enum sincronizado con `backend/.../accounts/models.py`.
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

/** Tipos `asset` (dinero disponible). */
export const ASSET_ACCOUNT_TYPES: readonly AccountType[] = [
  'bank',
  'savings',
  'brokerage',
  'crypto',
  'cash',
] as const;

/** Tipos `liability` (deuda). PHASE-22. */
export const LIABILITY_ACCOUNT_TYPES: readonly AccountType[] = [
  'credit_card',
  'loan',
  'mortgage',
] as const;

/** Cualquier tipo que el form expone al usuario. */
export const SELECTABLE_ACCOUNT_TYPES: readonly AccountType[] = [
  ...ASSET_ACCOUNT_TYPES,
  ...LIABILITY_ACCOUNT_TYPES,
] as const;

/** Tipos a los que aplica el cuadro francés (apr/term/start_date). */
export const AMORTIZABLE_ACCOUNT_TYPES: readonly AccountType[] = [
  'loan',
  'mortgage',
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
  /** APR anual decimal (0.0350 = 3.50%). Sólo loan/mortgage. */
  apr: string | null;
  /** Plazo total en meses. Sólo loan/mortgage. */
  term_months: number | null;
  /** YYYY-MM-DD. Inicio del préstamo. Sólo loan/mortgage. */
  start_date: string | null;
  display_order: number;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
}
