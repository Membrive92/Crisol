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

/** Tipos a los que aplica el cuadro francés (apr/term/start_date).
 * PHASE-24.2: tarjetas financiadas también lo aceptan. */
export const AMORTIZABLE_ACCOUNT_TYPES: readonly AccountType[] = [
  'loan',
  'mortgage',
  'credit_card',
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
  /** TIN anual decimal (0.0350 = 3.50% TIN). Sólo tipos amortizables. */
  apr: string | null;
  /** PHASE-24.2 — TAE anual decimal. Informativa, no afecta cálculo. */
  tae: string | null;
  /** Plazo total en meses. Sólo tipos amortizables. */
  term_months: number | null;
  /** YYYY-MM-DD. Inicio del préstamo. Sólo tipos amortizables. */
  start_date: string | null;
  /** PHASE-24.3 — Total contractualizado por el banco. */
  total_to_pay?: string | null;
  /** PHASE-24.3 — Primera cuota especial sólo de intereses. */
  interest_only_first_payment?: string | null;
  display_order: number;
  is_archived: boolean;
  /** PHASE-30.4 — Categoría de pagos vinculada (chip en Capa 2 de
   * /debt). NULL = sin vincular. Sólo significativo en liabilities. */
  category_id?: string | null;
  created_at: string;
  updated_at: string;
}
