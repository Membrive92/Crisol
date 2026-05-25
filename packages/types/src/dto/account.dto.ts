import type { AccountType } from '../models/account';

export interface AccountCreateRequest {
  name: string;
  type: AccountType;
  currency?: string;
  color?: string | null;
  icon?: string | null;
  opening_balance?: string;
  opening_balance_date?: string | null;
  /** TIN anual decimal. Sólo tipos amortizables (PHASE-24.2 incluye
   * credit_card para tarjetas financiadas). */
  apr?: string | null;
  /** PHASE-24.2 — TAE anual decimal, informativa. */
  tae?: string | null;
  term_months?: number | null;
  start_date?: string | null;
  /** PHASE-24.3 — Total contractualizado (banco). */
  total_to_pay?: string | null;
  /** PHASE-24.3 — Primer pago sólo de intereses. */
  interest_only_first_payment?: string | null;
  display_order?: number;
  /** PHASE-30.4 — Categoría de pagos vinculada. Sólo válida para
   * liabilities con role DEBT_PAYMENT o DEBT_INTEREST. */
  category_id?: string | null;
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
  tae?: string | null;
  term_months?: number | null;
  start_date?: string | null;
  total_to_pay?: string | null;
  interest_only_first_payment?: string | null;
  display_order?: number;
  is_archived?: boolean;
  /** PHASE-30.4 — Vincular o desvincular categoría (null para desvincular). */
  category_id?: string | null;
}
